"""
Market data retrieval service for RAG (Retrieval-Augmented Generation).
Ensures all statistics are grounded in live data sources.
Never returns stale data without explicit warning.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, Optional, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class MarketDataRetriever:
    """
    Retrieves grounded market context for chatbot responses.
    All retrievals tagged with source and freshness metadata.
    Implements three-tier fallback: specific delegation → national average → error.
    """
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour
    
    def get_market_context(self, location: str, 
                           location_type: str = 'delegation',
                           data_types: Optional[List[str]] = None,
                           property_type: str = 'apartment') -> Dict:
        """
        Retrieves all relevant market context for a location.
        
        data_types: list of ['market_snapshot', 'forecast', 'climate_risk', 
                             'investment_grade', 'legal_context']
                    If None, retrieves all.
        
        Returns grounded context dict with source attribution.
        """
        
        if not data_types:
            data_types = ['market_snapshot', 'forecast', 'climate_risk', 
                         'investment_grade']
        
        context = {}
        retrieval_errors = []
        
        if 'market_snapshot' in data_types:
            snap = self._get_market_snapshot(location, location_type)
            context['market'] = snap
            if not snap.get('available'):
                retrieval_errors.append(snap.get('reason', 'Unknown error'))
        
        if 'forecast' in data_types:
            fcast = self._get_forecast(location, location_type, property_type)
            context['forecast'] = fcast
            if not fcast.get('available'):
                retrieval_errors.append(fcast.get('reason', 'Unknown error'))
        
        if 'climate_risk' in data_types:
            climate = self._get_climate_risk(location)
            context['climate'] = climate
            if not climate.get('available'):
                retrieval_errors.append(climate.get('reason', 'Unknown error'))
        
        if 'investment_grade' in data_types:
            invest = self._get_investment_context(location)
            context['investment'] = invest
            if not invest.get('available'):
                retrieval_errors.append(invest.get('reason', 'Unknown error'))
        
        return {
            'context': context,
            'retrieval_errors': retrieval_errors,
            'is_fully_grounded': len(retrieval_errors) == 0,
            'retrieved_at': timezone.now().isoformat(),
            'location': location,
            'location_type': location_type
        }
    
    def _get_market_snapshot(self, location: str, location_type: str) -> Dict:
        """
        Retrieves current market snapshot for a delegation.
        Checks data freshness and warns if aging.
        """
        try:
            from estatemind.market.core.models import Delegation
            from estatemind.intelligence.simulation.services.market_service import (
                get_market_snapshot_for_delegation
            )
            
            # Find delegation
            d = Delegation.objects.filter(
                name__icontains=location
            ).first()
            
            if not d:
                return {
                    'available': False,
                    'reason': f'No delegation found matching "{location}"',
                    'fallback': 'national_average'
                }
            
            # Get market snapshot
            snapshot = get_market_snapshot_for_delegation(d.name)
            
            if not snapshot or snapshot.get('error'):
                return {
                    'available': False,
                    'reason': f'No market data available for {d.name}',
                    'fallback': 'national_average'
                }
            
            # Check data freshness
            snapshot_date = snapshot.get('as_of_date')
            if isinstance(snapshot_date, str):
                try:
                    snapshot_date = datetime.fromisoformat(snapshot_date).date()
                except:
                    snapshot_date = date.today()
            
            age_days = (date.today() - snapshot_date).days if snapshot_date else 0
            
            freshness = (
                'FRESH' if age_days < 7 else
                'ACCEPTABLE' if age_days < 30 else
                'STALE'
            )
            
            freshness_prefix = (
                '' if freshness == 'FRESH' else
                f'As of {snapshot_date}: ' if freshness == 'ACCEPTABLE' else
                f'Note: Data from {snapshot_date} (may be outdated). '
            )
            
            # Validate listing_count - must be positive integer
            listing_count = snapshot.get('listing_count', 0)
            try:
                listing_count = int(listing_count) if listing_count else 0
                if listing_count < 0:
                    listing_count = 0  # Invalid negative count
            except (ValueError, TypeError):
                listing_count = 0  # Invalid type
            
            # Detect impossible condition: no listings but median price exists
            median_price_per_sqm = snapshot.get('median_price_per_sqm', 0)
            median_price_total = snapshot.get('median_price_total', 0)
            is_impossible_state = (listing_count == 0 and (median_price_per_sqm > 0 or median_price_total > 0))
            if is_impossible_state:
                logger.warning(f'Impossible market state detected for {d.name}: listing_count=0 but median_price exists')
            
            return {
                'available': True,
                'delegation': d.name,
                'median_price_per_sqm': median_price_per_sqm,
                'median_price_total': median_price_total,
                'listing_count': listing_count,
                'listing_count_valid': listing_count > 0,
                'impossible_state': is_impossible_state,  # Flag impossible scenarios
                'supply_pressure': snapshot.get('supply_pressure', 'unknown'),
                'trend_direction': snapshot.get('trend_direction', 'stable'),
                'trend_pct': snapshot.get('trend_pct', 0),
                'as_of_date': str(snapshot_date) if snapshot_date else date.today().isoformat(),
                'age_days': age_days,
                'freshness': freshness,
                'source_tag': f'market_snapshot_{snapshot_date}',
                'freshness_prefix': freshness_prefix
            }
            
        except Exception as e:
            logger.warning(f'Market snapshot retrieval failed for {location}: {e}')
            return {
                'available': False,
                'reason': f'Market data retrieval error: {str(e)[:100]}',
                'fallback': 'unable_to_retrieve'
            }
    
    def _get_forecast(self, location: str, location_type: str,
                      property_type: str = 'apartment') -> Dict:
        """
        Retrieves price forecast for location.
        """
        try:
            from estatemind.intelligence.forecast.services.forecast_service import (
                get_delegation_forecast
            )
            
            forecast = get_delegation_forecast(
                delegation_name=location,
                property_type=property_type
            )
            
            if forecast and forecast.get('summary'):
                summary = forecast['summary']
                return {
                    'available': True,
                    'price_change_12m_pct': summary.get('price_change_pct', 0),
                    'trend_direction': summary.get('trend_direction', 'stable'),
                    'confidence': summary.get('confidence', 0.5),
                    'model_type': forecast.get('model_info', {}).get('model_type', 'unknown'),
                    'source_tag': f'forecast_{location}_{property_type}',
                    'forecasted_at': forecast.get('forecasted_at', timezone.now().isoformat())
                }
            else:
                return {
                    'available': False,
                    'reason': f'No forecast data available for {location}'
                }
                
        except Exception as e:
            logger.warning(f'Forecast retrieval failed for {location}: {e}')
            return {
                'available': False,
                'reason': f'Forecast retrieval error: {str(e)[:100]}'
            }
    
    def _get_climate_risk(self, location: str) -> Dict:
        """
        Retrieves climate risk score for delegation.
        """
        try:
            from estatemind.market.core.models import Delegation, DelegationClimateScore
            
            d = Delegation.objects.filter(name__icontains=location).first()
            if not d:
                return {
                    'available': False,
                    'reason': f'No delegation found for "{location}"'
                }
            
            score = DelegationClimateScore.objects.filter(
                delegation=d
            ).first()
            
            if not score:
                return {
                    'available': False,
                    'reason': f'No climate score available for {d.name}'
                }
            
            age_days = (timezone.now() - score.computed_at).days
            freshness = (
                'FRESH' if age_days < 30 else
                'ACCEPTABLE' if age_days < 90 else
                'STALE'
            )
            
            return {
                'available': True,
                'delegation': d.name,
                'composite_score': score.composite_score,
                'risk_label': score.risk_label,
                'flood_risk': score.flood_risk_score,
                'heat_stress': score.heat_stress_score,
                'coastal_erosion': score.coastal_erosion_score,
                'infrastructure_resilience': score.infrastructure_resilience_score,
                'wildfire_risk': score.wildfire_risk_score,
                'freshness': freshness,
                'computed_at': score.computed_at.isoformat(),
                'source_tag': f'climate_score_{score.computed_at.date()}',
                'ci_lower': score.ci_lower_95,
                'ci_upper': score.ci_upper_95
            }
            
        except Exception as e:
            logger.warning(f'Climate risk retrieval failed for {location}: {e}')
            return {
                'available': False,
                'reason': f'Climate retrieval error: {str(e)[:100]}'
            }
    
    def _get_investment_context(self, location: str) -> Dict:
        """
        Retrieves investment grade and opportunity context.
        """
        try:
            from estatemind.intelligence.investor.services.investment_service import (
                analyze_investment_opportunity
            )
            
            analysis = analyze_investment_opportunity(location)
            
            if analysis and analysis.get('grade'):
                return {
                    'available': True,
                    'delegation': location,
                    'grade': analysis.get('grade'),
                    'opportunity_score': analysis.get('opportunity_score', 0),
                    'risk_level': analysis.get('risk_level', 'unknown'),
                    'rental_yield_potential': analysis.get('rental_yield_potential', 0),
                    'capital_appreciation': analysis.get('capital_appreciation', 0),
                    'source_tag': 'investment_analysis',
                    'analyzed_at': timezone.now().isoformat()
                }
            else:
                return {
                    'available': False,
                    'reason': f'No investment analysis available for {location}'
                }
                
        except Exception as e:
            logger.warning(f'Investment analysis failed for {location}: {e}')
            return {
                'available': False,
                'reason': f'Investment analysis error: {str(e)[:100]}'
            }
    
    def get_national_rankings(self, data_types: Optional[List[str]] = None,
                             property_type: str = 'apartment') -> Dict:
        """
        Retrieves nationwide rankings for queries without specific location.
        Used for queries like 'What are the top 5 delegations?'
        
        Returns top-performing delegations across various metrics.
        """
        if not data_types:
            data_types = ['market_snapshot', 'forecast', 'investment_grade']
        
        context = {}
        retrieval_errors = []
        
        try:
            if 'market_snapshot' in data_types:
                rankings = self._get_market_rankings(property_type)
                context['market'] = rankings
                if not rankings.get('available'):
                    retrieval_errors.append(rankings.get('reason', 'Unknown error'))
            
            if 'forecast' in data_types:
                top_growth = self._get_forecast_rankings(property_type)
                context['forecast'] = top_growth
                if not top_growth.get('available'):
                    retrieval_errors.append(top_growth.get('reason', 'Unknown error'))
            
            if 'investment_grade' in data_types:
                top_investments = self._get_investment_rankings()
                context['investment'] = top_investments
                if not top_investments.get('available'):
                    retrieval_errors.append(top_investments.get('reason', 'Unknown error'))
        
        except Exception as e:
            logger.error(f'National rankings retrieval failed: {e}')
            retrieval_errors.append(f'Ranking retrieval error: {str(e)[:100]}')
        
        return {
            'context': context,
            'retrieval_errors': retrieval_errors,
            'is_fully_grounded': len(retrieval_errors) == 0,
            'retrieved_at': timezone.now().isoformat(),
            'location': 'NATIONWIDE',
            'location_type': 'national'
        }
    
    def _get_market_rankings(self, property_type: str) -> Dict:
        """Get top 10 most expensive delegations by median price per sqm."""
        try:
            from estatemind.market.features.models import DelegationStats
            
            rankings = (
                DelegationStats.objects
                .filter(property_type=property_type)
                .order_by('-median_price_per_m2')[:10]
            )
            
            if not rankings:
                return {
                    'available': False,
                    'reason': 'No market ranking data available'
                }
            
            top_delegations = [
                {
                    'rank': i + 1,
                    'delegation': r.delegation_name,
                    'governorate': r.governorate,
                    'median_price_per_sqm': r.median_price_per_m2,
                    'listing_count': r.listing_count
                }
                for i, r in enumerate(rankings)
            ]
            
            return {
                'available': True,
                'ranking_type': 'most_expensive_by_median_ppm2',
                'top_delegations': top_delegations,
                'property_type': property_type,
                'source_tag': f'market_rankings_{property_type}',
                'retrieved_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.warning(f'Market rankings failed: {e}')
            return {
                'available': False,
                'reason': f'Market ranking error: {str(e)[:100]}'
            }
    
    def _get_forecast_rankings(self, property_type: str) -> Dict:
        """Get top 10 fastest growing delegations by 12-month forecast growth."""
        try:
            from estatemind.intelligence.forecast.models import DelegationForecast, DelegationPriceData
            from django.db.models import F, FloatField, Case, When
            from django.db.models.functions import Coalesce
            
            # Get latest forecast per delegation
            forecasts = (
                DelegationForecast.objects
                .filter(property_type=property_type)
                .order_by('delegation_name', '-forecast_month')
                .distinct('delegation_name')
            )
            
            # Calculate growth rates
            rankings = []
            for f in forecasts[:20]:  # Check top 20, filter to top 10
                if f.predicted_price_per_m2 > 0:
                    # Get initial price from DelegationPriceData
                    initial_price = (
                        DelegationPriceData.objects
                        .filter(
                            delegation_name=f.delegation_name,
                            property_type=property_type
                        )
                        .values_list('price_avg', flat=True)
                        .first()
                    )
                    
                    if initial_price and initial_price > 0:
                        predicted_tnd = f.predicted_price_per_m2 / 1000  # Convert from millimes
                        growth_pct = ((predicted_tnd - initial_price) / initial_price) * 100
                        rankings.append({
                            'delegation': f.delegation_name,
                            'growth_pct_12m': round(growth_pct, 2),
                            'current_price': round(initial_price, 2),
                            'forecast_price': round(predicted_tnd, 2)
                        })
            
            if not rankings:
                return {
                    'available': False,
                    'reason': 'No forecast ranking data available'
                }
            
            # Sort by growth and take top 10
            rankings.sort(key=lambda x: x['growth_pct_12m'], reverse=True)
            top_rankings = rankings[:10]
            
            for i, r in enumerate(top_rankings):
                r['rank'] = i + 1
            
            return {
                'available': True,
                'ranking_type': 'fastest_growing_12m',
                'top_delegations': top_rankings,
                'property_type': property_type,
                'source_tag': 'forecast_rankings',
                'retrieved_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.warning(f'Forecast rankings failed: {e}')
            return {
                'available': False,
                'reason': f'Forecast ranking error: {str(e)[:100]}'
            }
    
    def _get_investment_rankings(self) -> Dict:
        """Get top 10 investment opportunities nationwide."""
        try:
            from estatemind.intelligence.investor.services.zone_data import ZoneAnalyzer
            
            analyzer = ZoneAnalyzer()
            top_zones = analyzer.get_top_investment_zones(limit=10)
            
            if not top_zones:
                return {
                    'available': False,
                    'reason': 'No investment ranking data available'
                }
            
            return {
                'available': True,
                'ranking_type': 'best_investment_opportunities',
                'top_delegations': top_zones,
                'source_tag': 'investment_rankings',
                'retrieved_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.warning(f'Investment rankings failed: {e}')
            return {
                'available': False,
                'reason': f'Investment ranking error: {str(e)[:100]}'
            }

