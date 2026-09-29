"""
Module 7 Scoring Services — 7 Investment Models
================================================

Each service implements one of the 7 investor scoring models.
All models are called as part of two chains: Scanner and Portfolio.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple

import numpy as np
from django.utils import timezone

logger = logging.getLogger(__name__)


class BaseScorerService(ABC):
    """Abstract base for all scorer services."""

    @abstractmethod
    def score(self, **kwargs) -> Dict[str, Any]:
        """Compute score. Returns dict with 'value', 'label', 'confidence', 'drivers'."""
        pass


# ════════════════════════════════════════════════════════════════════════════════
# Model 1: Undervaluation Detector
# ════════════════════════════════════════════════════════════════════════════════

class UndervaluationDetectorService(BaseScorerService):
    """
    Compares asking price to market reference value.
    Reference = median_price_per_sqm × property_characteristics_adjustments
    """

    CONDITION_MULTIPLIERS = {
        'excellent': 1.12,
        'good': 1.00,
        'fair': 0.88,
        'poor': 0.75,
    }

    PROPERTY_TYPE_ADJUSTMENTS = {
        'apartment': 1.00,
        'villa': 1.15,
        'house': 1.05,
        'land': 0.80,
    }

    def score(self, asking_price_tnd: float, delegation_median_price_m2: float,
              surface_m2: float, condition: str = 'good', age_years: int = 15,
              property_type: str = 'apartment', **kwargs) -> Dict[str, Any]:
        """
        Score undervaluation.
        
        Returns:
          value: -0.30 (30% overvalued) to +0.30 (30% undervalued)
          label: 'overvalued' | 'fairly_priced' | 'undervalued' | 'strongly_undervalued'
          confidence: high/medium/low
          drivers: breakdown of reference value computation
        """
        try:
            # Reference value = median × size × condition × age_discount × type
            condition_mult = self.CONDITION_MULTIPLIERS.get(condition, 1.0)
            type_mult = self.PROPERTY_TYPE_ADJUSTMENTS.get(property_type, 1.0)
            
            # Age discount: properties 1-2 years old get 5% premium, 
            # properties >20 years get 10% discount
            if age_years <= 2:
                age_discount = 1.05
            elif age_years <= 5:
                age_discount = 1.02
            elif age_years <= 20:
                age_discount = 1.0
            else:
                age_discount = 1.0 - min((age_years - 20) * 0.01, 0.10)

            reference_value_per_m2 = (delegation_median_price_m2 
                                       * condition_mult 
                                       * age_discount 
                                       * type_mult)

            reference_value_total = reference_value_per_m2 * surface_m2

            # Undervaluation score: (ref - asking) / ref
            undervaluation_score = (reference_value_total - asking_price_tnd) / reference_value_total

            # Classify
            if undervaluation_score > 0.20:
                label = 'strongly_undervalued'
            elif undervaluation_score > 0.10:
                label = 'undervalued'
            elif undervaluation_score > -0.05:
                label = 'fairly_priced'
            else:
                label = 'overvalued'

            return {
                'value': min(max(undervaluation_score, -0.30), 0.30),
                'label': label,
                'confidence': 'high',
                'drivers': {
                    'reference_value_per_m2': round(reference_value_per_m2, 2),
                    'reference_value_total': round(reference_value_total, 2),
                    'asking_price': asking_price_tnd,
                    'discount_pct': round(undervaluation_score * 100, 1),
                    'condition_adjustment': condition_mult,
                    'age_adjustment': age_discount,
                    'type_adjustment': type_mult,
                },
            }

        except Exception as e:
            logger.error(f'Undervaluation detector error: {e}')
            return {
                'value': 0.0,
                'label': 'error',
                'confidence': 'low',
                'drivers': {'error': str(e)},
            }


# ════════════════════════════════════════════════════════════════════════════════
# Model 2: Yield Estimator
# ════════════════════════════════════════════════════════════════════════════════

class YieldEstimatorService(BaseScorerService):
    """
    Estimates gross and net rental yield.
    Gross = (monthly_rent × 12) / purchase_price
    Net = (gross - operating costs) / purchase_price
    """

    # Operating cost assumptions (as % of property value per year)
    MAINTENANCE_PCT_ANNUAL = 0.005  # 0.5% for maintenance
    VACANCY_ALLOWANCE_PCT = 1.0 / 12.0  # 1 month/year = 8.3%
    MANAGEMENT_FEE_PCT = 0.08  # 8% of rent if professionally managed
    INSURANCE_PCT_ANNUAL = 0.003  # 0.3% for insurance

    def score(self, purchase_price_tnd: float, delegation_median_monthly_rent: float,
              surface_m2: float, room_count: int = 3, property_type: str = 'apartment',
              is_self_managed: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Score rental yield.
        
        Returns:
          gross_yield_pct: (rent × 12) / price
          net_yield_pct: after operating costs
          confidence: high/medium/low (depends on rental data sample size)
          drivers: breakdown of costs
        """
        try:
            # Estimate monthly rent from delegation median, adjusted for property size/type
            # Larger properties get slight discount per sqm, premium for villas
            size_adjustment = 0.95 if surface_m2 > 150 else 1.0
            type_adjustment = 1.15 if property_type == 'villa' else 1.0

            estimated_monthly_rent = (delegation_median_monthly_rent 
                                     * size_adjustment 
                                     * type_adjustment)

            # Gross yield
            annual_rent = estimated_monthly_rent * 12
            gross_yield_pct = (annual_rent / purchase_price_tnd) * 100

            # Net yield: subtract operating costs
            maintenance_annual = purchase_price_tnd * self.MAINTENANCE_PCT_ANNUAL
            vacancy_loss = annual_rent * self.VACANCY_ALLOWANCE_PCT
            mgmt_fee = 0 if is_self_managed else (annual_rent * self.MANAGEMENT_FEE_PCT)
            insurance_annual = purchase_price_tnd * self.INSURANCE_PCT_ANNUAL

            total_opex = maintenance_annual + vacancy_loss + mgmt_fee + insurance_annual
            net_rent = annual_rent - total_opex
            net_yield_pct = (net_rent / purchase_price_tnd) * 100

            # Confidence depends on data quality
            # For now: assume medium unless we have signal otherwise
            confidence = 'medium'

            # Cap monthly rental income display at 500K TND (indicates data quality issue)
            display_monthly_rent = estimated_monthly_rent
            if estimated_monthly_rent > 500000:
                logger.warning(f'Estimated monthly rent {estimated_monthly_rent} exceeds 500K TND cap - data quality issue detected')
                display_monthly_rent = 500000  # Cap for display

            return {
                'gross_yield_pct': round(gross_yield_pct, 2),
                'net_yield_pct': round(net_yield_pct, 2),
                'estimated_monthly_rent': round(display_monthly_rent, 2),
                'actual_monthly_rent': round(estimated_monthly_rent, 2),  # Store actual for calculations
                'confidence': confidence,
                'drivers': {
                    'annual_rent': round(annual_rent, 2),
                    'maintenance': round(maintenance_annual, 2),
                    'vacancy_loss': round(vacancy_loss, 2),
                    'management_fee': round(mgmt_fee, 2),
                    'insurance': round(insurance_annual, 2),
                    'total_opex': round(total_opex, 2),
                    'net_annual_rent': round(net_rent, 2),
                },
            }

        except Exception as e:
            logger.error(f'Yield estimator error: {e}')
            return {
                'gross_yield_pct': 0.0,
                'net_yield_pct': 0.0,
                'confidence': 'low',
                'drivers': {'error': str(e)},
            }


# ════════════════════════════════════════════════════════════════════════════════
# Model 3: Buy/Wait Classifier (Base Rule Version)
# Will be upgraded to Offline RL in Hardening 2
# ════════════════════════════════════════════════════════════════════════════════

class BuyWaitClassifierService(BaseScorerService):
    """
    Classifies timing recommendation: BUY | WAIT | AVOID.
    Current implementation: rule-based thresholds.
    Future: Offline RL trained on historical investor outcomes.
    """

    def score(self, delegation_price_momentum_12m: float, undervaluation_score: float,
              estimated_net_yield: float, climate_risk_score: float,
              national_interest_rate: float = 8.0, delegation_dom: float = 30.0,
              **kwargs) -> Dict[str, Any]:
        """
        Score buy/wait recommendation.
        
        Current rules:
          BUY: momentum > +5% AND underval > 10% AND yield > 3.5% AND climate < 0.6
          WAIT: momentum declining OR overvalued OR high interest rates
          AVOID: climate > 0.75 OR yield < 2%
        
        Note: This will be replaced by LightGBM classifier in hardening.
        """
        try:
            signal = 'WAIT'  # default
            confidence = 0.5

            # Quick rule-based logic
            has_positive_momentum = delegation_price_momentum_12m > 0.05
            has_undervaluation = undervaluation_score > 0.10
            has_good_yield = estimated_net_yield > 3.5
            climate_ok = climate_risk_score < 0.6
            rates_acceptable = national_interest_rate < 9.0

            buy_signals = sum([has_positive_momentum, has_undervaluation, 
                              has_good_yield, climate_ok, rates_acceptable])

            if buy_signals >= 4:
                signal = 'BUY'
                confidence = 0.6 + (buy_signals - 4) * 0.1
            elif climate_risk_score > 0.75 or estimated_net_yield < 2.0:  # yield is in percent
                signal = 'AVOID'
                confidence = 0.7
            else:
                signal = 'WAIT'
                confidence = 0.5

            return {
                'signal': signal,
                'confidence': min(confidence, 0.95),
                'label': f'{signal} (rule-based)',
                'drivers': {
                    'positive_momentum': has_positive_momentum,
                    'undervaluation': has_undervaluation,
                    'good_yield': has_good_yield,
                    'climate_ok': climate_ok,
                    'rates_acceptable': rates_acceptable,
                    'signal_count': buy_signals,
                },
            }

        except Exception as e:
            logger.error(f'Buy/wait classifier error: {e}')
            return {
                'signal': 'WAIT',
                'confidence': 0.3,
                'label': 'error',
                'drivers': {'error': str(e)},
            }


# ════════════════════════════════════════════════════════════════════════════════
# Model 4: Opportunity Scorer (Composite)
# ════════════════════════════════════════════════════════════════════════════════

class OpportunityScorerService(BaseScorerService):
    """
    Composite opportunity score combining 5 dimensions:
      - Undervaluation (30%)
      - Yield (25%)
      - Market Trend (25%)
      - Liquidity (10%)
      - Climate (10%)
    
    Each component normalized to [0, 100] then weighted.
    """

    WEIGHTS = {
        'undervaluation': 0.30,
        'yield': 0.25,
        'trend': 0.25,
        'liquidity': 0.10,
        'climate': 0.10,
    }

    def score(self, undervaluation_score: float, net_yield_pct: float,
              delegation_price_momentum_12m: float, delegation_dom: float,
              climate_risk_score: float, **kwargs) -> Dict[str, Any]:
        """
        Compute composite opportunity score [0, 100].
        """
        try:
            # Normalize each component to [0, 100]
            
            # Undervaluation: -0.30 → 0, 0 → 50, +0.30 → 100
            underval_component = (undervaluation_score + 0.30) / 0.60 * 100
            underval_component = max(0, min(100, underval_component))

            # Yield: 0% → 0, 5% → 100
            yield_component = min(net_yield_pct / 5.0 * 100, 100)

            # Trend: -10% → 0, 0% → 50, +20% → 100
            trend_component = (delegation_price_momentum_12m + 0.10) / 0.30 * 100
            trend_component = max(0, min(100, trend_component))

            # Liquidity (lower DOM is better): 90 days → 0, 30 days → 100
            liquidity_component = max(0, (90 - delegation_dom) / 60 * 100)

            # Climate risk (lower is better): 0.75 → 0, 0.0 → 100
            climate_component = (0.75 - climate_risk_score) / 0.75 * 100
            climate_component = max(0, min(100, climate_component))

            # Compute weighted score
            opportunity_score = (
                underval_component * self.WEIGHTS['undervaluation'] +
                yield_component * self.WEIGHTS['yield'] +
                trend_component * self.WEIGHTS['trend'] +
                liquidity_component * self.WEIGHTS['liquidity'] +
                climate_component * self.WEIGHTS['climate']
            )

            return {
                'value': round(opportunity_score, 1),
                'confidence': 'high',
                'breakdown': {
                    'undervaluation': round(underval_component, 1),
                    'yield': round(yield_component, 1),
                    'trend': round(trend_component, 1),
                    'liquidity': round(liquidity_component, 1),
                    'climate': round(climate_component, 1),
                },
                'drivers': {
                    'undervaluation_score': undervaluation_score,
                    'net_yield_pct': net_yield_pct,
                    'momentum_12m': delegation_price_momentum_12m,
                    'dom': delegation_dom,
                    'climate_risk': climate_risk_score,
                },
            }

        except Exception as e:
            logger.error(f'Opportunity scorer error: {e}')
            return {
                'value': 50.0,
                'confidence': 'low',
                'breakdown': {},
                'drivers': {'error': str(e)},
            }


# ════════════════════════════════════════════════════════════════════════════════
# Model 5: Investment Grader
# ════════════════════════════════════════════════════════════════════════════════

class InvestmentGraderService(BaseScorerService):
    """
    Converts opportunity score [0, 100] to letter grade A/B/C/D/F.
    Thresholds calibrated by CalibrationAuditService.
    """

    THRESHOLDS = {
        'A': 85,  # 85-100
        'B': 70,  # 70-84
        'C': 55,  # 55-69
        'D': 40,  # 40-54
        'F': 0,   # 0-39
    }

    GRADE_LABELS = {
        'A': 'Strong Buy',
        'B': 'Buy',
        'C': 'Hold',
        'D': 'Wait',
        'F': 'Avoid',
    }

    def score(self, opportunity_score: float, **kwargs) -> Dict[str, Any]:
        """
        Assign letter grade based on opportunity score.
        """
        try:
            grade = 'F'
            for g in ['A', 'B', 'C', 'D', 'F']:
                if opportunity_score >= self.THRESHOLDS[g]:
                    grade = g
                    break

            # Compute sub-grade (e.g., B+, B, B-)
            grade_range = {
                'A': (85, 100),
                'B': (70, 84),
                'C': (55, 69),
                'D': (40, 54),
                'F': (0, 39),
            }

            lower, upper = grade_range[grade]
            range_size = upper - lower + 1
            position_in_range = opportunity_score - lower

            if position_in_range / range_size >= 0.67:
                sub_grade = '+'
            elif position_in_range / range_size >= 0.33:
                sub_grade = ''
            else:
                sub_grade = '-'

            full_grade = grade + sub_grade

            return {
                'grade': full_grade,
                'label': self.GRADE_LABELS[grade],
                'confidence': 'high',
                'drivers': {
                    'opportunity_score': opportunity_score,
                    'grade_thresholds': self.THRESHOLDS,
                },
            }

        except Exception as e:
            logger.error(f'Investment grader error: {e}')
            return {
                'grade': 'F',
                'label': 'Error',
                'confidence': 'low',
                'drivers': {'error': str(e)},
            }


# ════════════════════════════════════════════════════════════════════════════════
# Model 6: IRR Calculator
# ════════════════════════════════════════════════════════════════════════════════

IRR_SCENARIO_NOTE = ('Base uses the central 12-month price forecast; pessimistic and optimistic use '
                     "the low and high end of the forecast's band. The band is illustrative: the "
                     "forecast's accuracy has not been measured.")
IRR_NO_BAND_NOTE = ('Base, pessimistic and optimistic IRR are identical because the forecast for this '
                    'place has no band, not because the scenarios agree.')
IRR_NO_GROWTH_NOTE = ('No price forecast is available for this place, so the IRR assumes 0% price '
                      'growth and the three scenarios are identical.')


class IRRCalculatorService(BaseScorerService):
    """
    Computes Internal Rate of Return for a buy-and-hold investment.
    
    Assumptions:
      - Down payment: 30%
      - Loan term: 20 years
      - Loan interest: 8% annual
      - Annual appreciation: from price forecast
      - Annual rent: from yield estimator
      - Holding period: user-configurable (default 10 years)
    """

    def score(self, purchase_price_tnd: float, annual_rent_tnd: float,
              annual_appreciation_pct: float | None, holding_years: int = 10,
              down_payment_pct: float = 0.30, loan_interest_rate: float = 0.08,
              annual_appreciation_low_pct: float | None = None,
              annual_appreciation_high_pct: float | None = None,
              **kwargs) -> Dict[str, Any]:
        """
        Compute IRR (base case, pessimistic, optimistic).

        Base: the forecast growth. Pessimistic / optimistic: the low and high end of
        the forecast's 12-month band. (They used to be 0% and 1.5x the base, so with a
        falling forecast the 'optimistic' case was the worst.) Without a band the
        three coincide, and without any growth estimate growth is 0%; both are said
        in scenario_note.
        """
        try:
            # Cash flow calculation
            def compute_irr_for_appreciation(annual_appreciation):
                cash_flows = []

                # Year 0: purchase (negative)
                purchase_cost = purchase_price_tnd * (1 + 0.10)  # 10% transaction costs
                down_payment = purchase_cost * down_payment_pct
                loan_amount = purchase_cost - down_payment
                cash_flows.append(-down_payment)  # Only down payment in year 0

                # Years 1-N: rental income - financing costs
                remaining_loan = loan_amount
                for year in range(1, holding_years + 1):
                    annual_interest = remaining_loan * loan_interest_rate
                    annual_principal = loan_amount / 20  # 20-year amortization

                    net_rent = annual_rent_tnd * (1 - 0.083 - 0.08 - 0.005)  # vacancy, mgmt, maintenance
                    financing_cost = annual_interest

                    if year <= 20:
                        year_cash_flow = net_rent - financing_cost
                    else:
                        year_cash_flow = net_rent  # Loan fully paid

                    cash_flows.append(year_cash_flow)
                    remaining_loan -= annual_principal

                # Final year: sale
                final_value = purchase_price_tnd * ((1 + annual_appreciation) ** holding_years)
                final_value_after_costs = final_value * 0.96  # 4% exit costs
                cash_flows[-1] += final_value_after_costs - remaining_loan

                # Compute IRR using numpy-financial-like approach
                # Simple Newton-Raphson IRR solver
                irr = self._compute_irr_newton(cash_flows)
                return irr

            has_growth = annual_appreciation_pct is not None
            base = annual_appreciation_pct if has_growth else 0.0
            low = annual_appreciation_low_pct if annual_appreciation_low_pct is not None else base
            high = annual_appreciation_high_pct if annual_appreciation_high_pct is not None else base
            low, high = min(low, base), max(high, base)
            irr_base = compute_irr_for_appreciation(base / 100)
            irr_pessimistic = compute_irr_for_appreciation(low / 100)
            irr_optimistic = compute_irr_for_appreciation(high / 100)

            scenarios_identical = low == base == high
            note = (IRR_NO_GROWTH_NOTE if not has_growth
                    else IRR_NO_BAND_NOTE if scenarios_identical else IRR_SCENARIO_NOTE)
            return {
                'irr_base_pct': round(irr_base * 100, 2),
                'irr_pessimistic_pct': round(irr_pessimistic * 100, 2),
                'irr_optimistic_pct': round(irr_optimistic * 100, 2),
                'scenarios_identical': scenarios_identical,
                'scenario_note': note,
                'holding_years': holding_years,
                'confidence': 'medium',
                'drivers': {
                    'purchase_price': purchase_price_tnd,
                    'annual_rent': annual_rent_tnd,
                    'annual_appreciation': base,
                    'annual_appreciation_low': low,
                    'annual_appreciation_high': high,
                    'down_payment_pct': down_payment_pct * 100,
                    'loan_interest_rate': loan_interest_rate * 100,
                },
            }

        except Exception as e:
            logger.error(f'IRR calculator error: {e}')
            return {
                'irr_base_pct': 0.0,
                'irr_pessimistic_pct': 0.0,
                'irr_optimistic_pct': 0.0,
                'confidence': 'low',
                'drivers': {'error': str(e)},
            }

    @staticmethod
    def _compute_irr_newton(cash_flows: List[float], tolerance: float = 1e-6, max_iter: int = 100) -> float:
        """
        IRR by Newton-Raphson, falling back to bisection on (-99%, +100%) when Newton
        leaves that range or does not converge. (Newton alone diverged on leveraged
        cash flows with falling prices, overflowed, and the error handler reported
        0% for every scenario.)
        """
        def npv(rate, flows):
            return sum(cf / (1 + rate) ** i for i, cf in enumerate(flows))

        def npv_derivative(rate, flows):
            return sum(-i * cf / (1 + rate) ** (i + 1) for i, cf in enumerate(flows))

        rate = 0.1  # initial guess
        try:
            for _ in range(max_iter):
                npv_val = npv(rate, cash_flows)
                if abs(npv_val) < tolerance:
                    return rate
                npv_deriv = npv_derivative(rate, cash_flows)
                if npv_deriv == 0:
                    break
                rate -= npv_val / npv_deriv
                if not -0.99 < rate < 1.0:
                    break
        except (OverflowError, ZeroDivisionError):
            pass

        lo, hi = -0.99, 1.0
        f_lo, f_hi = npv(lo, cash_flows), npv(hi, cash_flows)
        if f_lo * f_hi > 0:  # no sign change: the return lies outside the range
            # negative at both ends: the cash flows never pay back (e.g. the sale does
            # not repay the loan), so the investment is a near-total loss
            return lo if f_lo < 0 else hi
        for _ in range(200):
            mid = (lo + hi) / 2
            f_mid = npv(mid, cash_flows)
            if abs(f_mid) < tolerance or hi - lo < 1e-9:
                return mid
            if f_lo * f_mid < 0:
                hi = mid
            else:
                lo, f_lo = mid, f_mid
        return (lo + hi) / 2


# ════════════════════════════════════════════════════════════════════════════════
# Model 7: Portfolio Risk Assessor (Base Version)
# Will be upgraded by Portfolio Covariance Model in Hardening 3
# ════════════════════════════════════════════════════════════════════════════════

class PortfolioRiskAssessorService(BaseScorerService):
    """
    Initial implementation: simple aggregation of individual asset risks.
    Will be upgraded with covariance matrix analysis in Hardening 3.
    """

    def score(self, asset_grades: List[str], asset_values: List[float],
              delegations: List[str], **kwargs) -> Dict[str, Any]:
        """
        Score portfolio risk based on diversification and concentration.
        """
        try:
            total_value = sum(asset_values)
            weights = [v / total_value for v in asset_values]

            # Concentration: % in top delegation
            delegation_values = {}
            for delegation, value in zip(delegations, asset_values):
                delegation_values[delegation] = delegation_values.get(delegation, 0) + value

            max_delegation_pct = max(delegation_values.values()) / total_value * 100

            # Simple risk score: concentration + grade mix
            grade_scores = {'A': 20, 'B': 50, 'C': 70, 'D': 85, 'F': 100}
            avg_grade_risk = sum(grade_scores.get(g[0], 50) * w for g, w in zip(asset_grades, weights))

            risk_score = (avg_grade_risk * 0.6 + max_delegation_pct * 0.4)

            if risk_score < 40:
                risk_label = 'low'
            elif risk_score < 60:
                risk_label = 'medium'
            else:
                risk_label = 'high'

            return {
                'risk_score': round(risk_score, 1),
                'risk_label': risk_label,
                'concentration_pct': round(max_delegation_pct, 1),
                'unique_delegations': len(delegation_values),
                'drivers': {
                    'asset_count': len(asset_values),
                    'total_value': total_value,
                    'diversification_ratio': len(delegation_values) / len(asset_values),
                },
            }

        except Exception as e:
            logger.error(f'Portfolio risk assessor error: {e}')
            return {
                'risk_score': 50.0,
                'risk_label': 'unknown',
                'drivers': {'error': str(e)},
            }
