"""
Scoring Chains
==============

Two main chains:
1. Scanner Chain: Evaluate a new listing property
2. Portfolio Chain: Evaluate portfolio holdings

Each chain composes the 7 scoring models in a specific order,
passing outputs as inputs to downstream models.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from estatemind.intelligence.investor.models import InvestmentScore, PortfolioAnalysis, InvestorScorerVersion
from estatemind.intelligence.investor.services.scoring_method import describe
from estatemind.intelligence.investor.services import (
    UndervaluationDetectorService,
    YieldEstimatorService,
    BuyWaitClassifierService,
    OpportunityScorerService,
    InvestmentGraderService,
    IRRCalculatorService,
    PortfolioRiskAssessorService,
    IRR_NO_GROWTH_NOTE,
    IRR_SCENARIO_NOTE,
)

logger = logging.getLogger(__name__)


class ScannerChain:
    """
    Chain for evaluating a single property (new listing).
    
    Flow: M1 → M3 → M2 → M4 → M5 → Output
    """

    def __init__(self):
        self.m1 = UndervaluationDetectorService()
        self.m2 = YieldEstimatorService()
        self.m3 = BuyWaitClassifierService()
        self.m4 = OpportunityScorerService()
        self.m5 = InvestmentGraderService()
        self.m6 = IRRCalculatorService()

    def _apply_verdict_overrides(self, result: Dict[str, Any], property_data: Dict[str, Any],
                                 market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply hard logic overrides for impossible or extreme pricing.
        Overrides take precedence over model-based verdicts.
        """
        asking_price = property_data.get('asking_price_tnd', 0)
        surface_m2 = property_data.get('surface_m2', 1)
        market_median = market_data.get('delegation_median_price_m2', 1)
        
        if surface_m2 <= 0 or market_median <= 0:
            return result
        
        price_per_sqm = asking_price / surface_m2
        price_vs_market_pct = (price_per_sqm / market_median - 1) * 100
        
        MAX_REALISTIC_PRICE_PER_SQM = 15_000  # Carthage luxury ceiling
        
        # Hard override: impossible pricing by absolute standard
        if price_per_sqm > MAX_REALISTIC_PRICE_PER_SQM:
            result['recommendation'] = 'INVALID'
            result['investment_grade'] = 'F'
            result['key_drivers'] = [
                f'Price per m² ({price_per_sqm:,.0f} TND) exceeds realistic market maximum.',
                'Verify the asking price before proceeding.'
            ]
            logger.warning(f'Verdict override: price/m² {price_per_sqm:,.0f} exceeds max')
            return result
        
        # Hard override: extreme overpricing vs market
        if price_vs_market_pct > 200:  # >3x market value
            result['recommendation'] = 'Avoid'
            result['investment_grade'] = 'D'
            result['key_drivers'] = [
                f'Price is {price_vs_market_pct:.0f}% above market value.',
                'This listing is not investable at current asking price.'
            ]
            logger.warning(f'Verdict override: price {price_vs_market_pct:.0f}% above market')
            return result
        
        # Hard override: significant overpricing
        if price_vs_market_pct > 50:  # >50% above market
            result['recommendation'] = 'Wait'
            result['investment_grade'] = 'D'
            result['key_drivers'] = [
                f'Price is {price_vs_market_pct:.0f}% above market.',
                'Significant price negotiation or market decline needed.'
            ]
            logger.warning(f'Verdict override: price {price_vs_market_pct:.0f}% above market')
        
        return result

    def _get_appreciation_rate(self, delegation: str, property_type: str) -> dict:
        """
        Pulls 12-month price appreciation rate from Module 6 forecast.
        Returns rate and source label for transparency in IRR output.
        """
        try:
            # Correct import path based on Module 6 implementation
            from estatemind.intelligence.forecast.services.forecast_service import get_delegation_forecast
            
            forecast = get_delegation_forecast(
                delegation_name=delegation,
                property_type=property_type
            )
            
            # Check if forecast data exists
            if forecast is None:
                raise ValueError('No forecast data available for this delegation')
            
            # Pull 12-month projected change from forecast summary
            summary = forecast.get('summary', {})
            change_pct = summary.get('price_change_pct')
            
            if change_pct is not None:
                return {
                    'rate': float(change_pct) / 100.0,
                    'source': 'module6_forecast',
                    'delegation': delegation,
                    'property_type': property_type,
                    'confidence': summary.get('confidence', 'unknown')
                }
            else:
                raise ValueError('price_change_pct missing from forecast summary')
                
        except ImportError as e:
            # Log the specific import error so it is visible, not silent
            logger.warning(
                f'Module 6 forecast import failed for {delegation}/{property_type}: {e}. '
                f'Using delegation snapshot trend fallback.'
            )
            return self._national_average_fallback(delegation)
            
        except Exception as e:
            logger.warning(
                f'Module 6 forecast unavailable for {delegation}/{property_type}: {e}. '
                f'Using delegation snapshot trend fallback.'
            )
            return self._national_average_fallback(delegation)

    def _national_average_fallback(self, delegation: str) -> dict:
        """
        Fallback when Module 6 is unavailable.
        Uses delegation market snapshot trend instead of hardcoded value.
        """
        try:
            from estatemind.market.core.models import DelegationMarketSnapshot, Delegation
            
            delegation_obj = Delegation.objects.filter(
                name__icontains=delegation
            ).first()
            
            if delegation_obj:
                # Use most recent snapshot trend as proxy
                snapshot = DelegationMarketSnapshot.objects.filter(
                    delegation=delegation_obj
                ).order_by('-as_of_date').first()
                
                if snapshot and hasattr(snapshot, 'price_trend_pct'):
                    return {
                        'rate': float(snapshot.price_trend_pct) / 100.0,
                        'source': 'delegation_snapshot_trend',
                        'delegation': delegation,
                        'confidence': 'low'
                    }
        except Exception:
            pass
        
        # Last resort: Tunisia historical average (~5% nominal)
        return {
            'rate': 0.05,
            'source': 'national_historical_average',
            'delegation': delegation,
            'confidence': 'very_low',
            'note': 'Using 5% national average. Module 6 forecast unavailable.'
        }

    def run(self, property_data: Dict[str, Any], market_data: Dict[str, Any],
            user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Run complete scanner chain on a property.
        
        Args:
            property_data: asking_price, surface_m2, property_type, room_count, condition, age_years
            market_data: delegation_median_price_m2, delegation_median_monthly_rent,
                        delegation_price_momentum_12m, delegation_dom, climate_risk_score,
                        national_interest_rate
            user_id: optional for logging prediction
        
        Returns: Complete investment analysis
        """
        try:
            # M1: Undervaluation
            underval_result = self.m1.score(
                asking_price_tnd=property_data.get('asking_price_tnd'),
                delegation_median_price_m2=market_data.get('delegation_median_price_m2'),
                surface_m2=property_data.get('surface_m2'),
                condition=property_data.get('condition', 'good'),
                age_years=property_data.get('age_years', 15),
                property_type=property_data.get('property_type', 'apartment'),
            )

            # M2: Yield
            yield_result = self.m2.score(
                purchase_price_tnd=property_data.get('asking_price_tnd'),
                delegation_median_monthly_rent=market_data.get('delegation_median_monthly_rent'),
                surface_m2=property_data.get('surface_m2'),
                room_count=property_data.get('room_count', 3),
                property_type=property_data.get('property_type', 'apartment'),
                is_self_managed=property_data.get('is_self_managed', False),
            )

            # M3: Buy/Wait (rule-based for now, will be RL-based after hardening)
            buy_wait_result = self.m3.score(
                delegation_price_momentum_12m=market_data.get('delegation_price_momentum_12m', 0.0),
                undervaluation_score=underval_result['value'],
                estimated_net_yield=yield_result['net_yield_pct'],
                climate_risk_score=market_data.get('climate_risk_score', 0.5),
                national_interest_rate=market_data.get('national_interest_rate', 8.0),
                delegation_dom=market_data.get('delegation_dom', 30.0),
            )

            # M4: Opportunity Score (composite)
            opportunity_result = self.m4.score(
                undervaluation_score=underval_result['value'],
                net_yield_pct=yield_result['net_yield_pct'],
                delegation_price_momentum_12m=market_data.get('delegation_price_momentum_12m', 0.0),
                delegation_dom=market_data.get('delegation_dom', 30.0),
                climate_risk_score=market_data.get('climate_risk_score', 0.5),
            )

            # M5: Grade
            grade_result = self.m5.score(
                opportunity_score=opportunity_result['value'],
            )

            # M6: IRR with live forecast integration
            appreciation = self._get_appreciation_rate(
                property_data.get('delegation', 'Tunisia'),
                property_data.get('property_type', 'apartment')
            )

            irr_result = self.m6.score(
                purchase_price_tnd=property_data.get('asking_price_tnd'),
                annual_rent_tnd=yield_result['estimated_monthly_rent'] * 12,
                annual_appreciation_pct=appreciation['rate'] * 100,
                holding_years=property_data.get('holding_years', 10),
            )
            # Add appreciation source to result for transparency
            irr_result['appreciation_rate_used'] = round(appreciation['rate'] * 100, 2)
            irr_result['appreciation_source'] = appreciation['source']
            irr_result['appreciation_confidence'] = appreciation.get('confidence', 'unknown')

            # Assemble complete result
            result = {
                'timestamp': datetime.utcnow().isoformat(),
                'property': property_data,
                'market': market_data,

                # Model outputs
                'undervaluation': underval_result,
                'yield': yield_result,
                'buy_signal': buy_wait_result,
                'opportunity': opportunity_result,
                'grade': grade_result,
                'irr': irr_result,

                # Summary
                'investment_grade': grade_result['grade'],
                'opportunity_score': opportunity_result['value'],
                'recommendation': buy_wait_result['signal'],
                'confidence': buy_wait_result['confidence'],

                # Key drivers
                'key_drivers': [
                    f"{underval_result['label']} (asking {underval_result['drivers'].get('discount_pct', 0):.1f}% {['below', 'at', 'above'][0 if underval_result['drivers'].get('discount_pct', 0) > 0 else 1]} market)",
                    f"Net yield: {yield_result['net_yield_pct']:.1f}%",
                    f"Trend: {market_data.get('delegation_price_momentum_12m', 0)*100:.1f}% YoY",
                    f"IRR base case: {irr_result['irr_base_pct']:.1f}%",
                ],
                'appreciation_source': appreciation['source'],
                'appreciation_confidence': appreciation.get('confidence', 'unknown'),
                # Module 7 services are rule-based thresholds (see services/__init__.py)
                **describe(None),
            }
            
            # Apply hard verdict overrides for impossible pricing
            result = self._apply_verdict_overrides(result, property_data, market_data)

            # Optional: Save to DB
            if user_id:
                try:
                    InvestmentScore.objects.create(
                        user_id=user_id,
                        property_price_tnd=property_data.get('asking_price_tnd'),
                        delegation=property_data.get('delegation'),
                        property_type=property_data.get('property_type'),
                        room_count=property_data.get('room_count', 3),
                        surface_m2=property_data.get('surface_m2'),
                        undervaluation_score=underval_result['value'],
                        undervaluation_label=underval_result.get('label'),
                        gross_yield_pct=yield_result['gross_yield_pct'],
                        net_yield_pct=yield_result['net_yield_pct'],
                        yield_confidence=yield_result.get('confidence'),
                        buy_signal=buy_wait_result.get('signal'),
                        buy_signal_confidence=buy_wait_result.get('confidence', 0.5),
                        opportunity_score=opportunity_result['value'],
                        score_breakdown=opportunity_result.get('breakdown', {}),
                        investment_grade=grade_result.get('grade', 'F'),
                        irr_base_pct=irr_result['irr_base_pct'],
                        irr_pessimistic_pct=irr_result['irr_pessimistic_pct'],
                        irr_optimistic_pct=irr_result['irr_optimistic_pct'],
                        risk_score=50.0,  # Will be computed by M7 later
                        full_analysis=result,
                    )
                except Exception as e:
                    logger.error(f'Failed to save InvestmentScore: {e}')

            return result

        except Exception as e:
            logger.error(f'Scanner chain error: {e}')
            return {
                'error': str(e),
                'recommendation': 'ERROR',
                'grade': 'F',
            }


class PortfolioChain:
    """
    Chain for evaluating portfolio holdings.
    
    Flow: M2 (per-asset) → M6 (per-asset) → M7 (aggregated)
    
    Output: blended yields, blended IRR, portfolio risk, diversification signals
    """

    def __init__(self):
        self.m2 = YieldEstimatorService()
        self.m6 = IRRCalculatorService()
        self.m7 = PortfolioRiskAssessorService()

    def run(self, portfolio_assets: List[Dict[str, Any]], market_data_map: Dict[str, Any],
            user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Run portfolio analysis chain.
        
        Args:
            portfolio_assets: List of asset dicts with all property details
            market_data_map: Dict mapping delegation → market data
            user_id: for saving PortfolioAnalysis
        
        Returns: Complete portfolio analysis
        """
        try:
            if not portfolio_assets:
                return {
                    'error': 'Empty portfolio',
                    'total_assets': 0,
                }

            total_value = sum(a.get('current_value_tnd', a.get('acquisition_price_tnd', 0))
                            for a in portfolio_assets)

            yields = []
            irrs = []
            irrs_low, irrs_high = [], []
            irr_details = []
            grades = []
            delegations = []

            asset_analyses = []

            for asset in portfolio_assets:
                delegation = asset.get('delegation', '')
                market = market_data_map.get(delegation, {})

                # Per-asset yield
                yield_result = self.m2.score(
                    purchase_price_tnd=asset.get('current_value_tnd', asset.get('acquisition_price_tnd')),
                    delegation_median_monthly_rent=market.get('delegation_median_monthly_rent', 0),
                    surface_m2=asset.get('surface_m2', 100),
                    room_count=asset.get('room_count', 3),
                    property_type=asset.get('property_type', 'apartment'),
                    is_self_managed=asset.get('is_self_managed', False),
                )

                # Per-asset IRR
                irr_result = self.m6.score(
                    purchase_price_tnd=asset.get('acquisition_price_tnd'),
                    annual_rent_tnd=asset.get('monthly_rent_tnd', 0) * 12,
                    annual_appreciation_pct=market.get('delegation_price_momentum_12m', 0) * 100,
                    holding_years=10,
                )

                yields.append(yield_result['net_yield_pct'])
                irrs.append(irr_result['irr_base_pct'])
                irr_details.append(irr_result)
                irrs_low.append(irr_result.get('irr_pessimistic_pct', irr_result['irr_base_pct']))
                irrs_high.append(irr_result.get('irr_optimistic_pct', irr_result['irr_base_pct']))
                grades.append('B')  # placeholder
                delegations.append(delegation)

                asset_analyses.append({
                    'property_name': asset.get('property_name'),
                    'delegation': delegation,
                    'value': asset.get('current_value_tnd', asset.get('acquisition_price_tnd')),
                    'yield': yield_result['net_yield_pct'],
                    'irr': irr_result['irr_base_pct'],
                })

            # Portfolio-level aggregation
            weights = [a.get('current_value_tnd', a.get('acquisition_price_tnd', 0)) / total_value
                      for a in portfolio_assets]

            blended_gross_yield = sum(y * w for y, w in zip(yields, weights))  # Simplified
            blended_net_yield = blended_gross_yield * 0.75  # Rough approximation
            blended_irr = sum(i * w for i, w in zip(irrs, weights))
            blended_irr_low = sum(i * w for i, w in zip(irrs_low, weights))
            blended_irr_high = sum(i * w for i, w in zip(irrs_high, weights))

            # M7: Portfolio Risk
            risk_result = self.m7.score(
                asset_grades=grades,
                asset_values=[a.get('current_value_tnd', a.get('acquisition_price_tnd', 0))
                            for a in portfolio_assets],
                delegations=delegations,
            )

            result = {
                'timestamp': datetime.utcnow().isoformat(),
                'portfolio': {
                    'total_value': total_value,
                    'asset_count': len(portfolio_assets),
                    'delegation_count': len(set(delegations)),
                },
                'returns': {
                    'blended_gross_yield_pct': round(blended_gross_yield, 2),
                    'blended_net_yield_pct': round(blended_net_yield, 2),
                    'blended_irr_pct': round(blended_irr, 2),
                    'irr_pessimistic_pct': round(blended_irr_low, 2),
                    'irr_optimistic_pct': round(blended_irr_high, 2),
                    # portfolio IRRs use delegation price momentum, currently a 0.0 placeholder
                    'irr_scenarios_identical': all(a.get('scenarios_identical') for a in irr_details),
                    'irr_scenario_note': (IRR_NO_GROWTH_NOTE if all(a.get('scenarios_identical') for a in irr_details)
                                          else IRR_SCENARIO_NOTE),
                },
                'risk': {
                    'risk_score': risk_result['risk_score'],
                    'risk_label': risk_result['risk_label'],
                    'concentration_pct': risk_result['concentration_pct'],
                    'unique_delegations': risk_result['unique_delegations'],
                },
                'assets': asset_analyses,
            }

            # Optional: Save to DB
            if user_id:
                try:
                    PortfolioAnalysis.objects.create(
                        user_id=user_id,
                        total_value_tnd=total_value,
                        asset_count=len(portfolio_assets),
                        delegation_count=len(set(delegations)),
                        blended_gross_yield_pct=blended_gross_yield,
                        blended_net_yield_pct=blended_net_yield,
                        blended_irr_pct=blended_irr,
                        irr_pessimistic_pct=blended_irr_low,
                        irr_optimistic_pct=blended_irr_high,
                        portfolio_volatility_pct=0.0,  # Will be computed by hardening
                        diversification_ratio=1.0,  # Will be computed by hardening
                        concentration_pct=risk_result['concentration_pct'],
                        climate_risk_score=0.5,
                        full_analysis=result,
                    )
                except Exception:
                    logger.exception('Failed to save PortfolioAnalysis')

            return result

        except Exception as e:
            logger.error(f'Portfolio chain error: {e}')
            return {
                'error': str(e),
            }
