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


# Delegations ranked nationally need at least this many real (not sample) listings.
MIN_REAL_LISTINGS = 5


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
    
    @staticmethod
    def _resolve_location(location: str):
        """(delegation, region) for a place name: exact delegation name first, then a
        governorate name (answered at governorate level), then a partial match.
        Accent- and case-insensitive."""
        from estatemind.intelligence.valuation.inference.location import plain
        from estatemind.market.core.models import Delegation, Region

        key = plain(location)
        if not key:
            return None, None
        for d in Delegation.objects.select_related('region'):
            if plain(d.name) == key:
                return d, d.region
        for r in Region.objects.all():
            if plain(r.governorate) == key:
                return None, r
        d = Delegation.objects.select_related('region').filter(name__icontains=location).first()
        return (d, d.region) if d else (None, None)

    def _get_market_snapshot(self, location: str, location_type: str) -> Dict:
        """Latest market snapshot (core.DelegationMarketSnapshot) for a delegation, or
        the median over a governorate's delegations. Says when the figures rest on
        EstateMind's price benchmarks (synthetic sample listings) rather than real ones.
        (This used to read a hard-coded table of six cities.)"""
        try:
            from statistics import median

            from estatemind.market.core.models import DelegationMarketSnapshot

            delegation, region = self._resolve_location(location)
            if delegation is None and region is None:
                return {'available': False, 'reason': f'I could not find a place called "{location}".',
                        'fallback': 'national_average'}
            qs = DelegationMarketSnapshot.objects.select_related('delegation__region').order_by('-as_of_date')
            if delegation is not None:
                snaps = [s for s in [qs.filter(delegation=delegation).first()] if s]
                name = delegation.name
            else:
                latest = qs.filter(delegation__region=region).values_list('as_of_date', flat=True).first()
                snaps = list(qs.filter(delegation__region=region, as_of_date=latest)) if latest else []
                name = region.governorate
            snaps = [s for s in snaps if s.median_price_per_sqm]
            if not snaps:
                return {'available': False, 'reason': f'There is no market data for {name} yet.',
                        'fallback': 'national_average'}

            ppm = median(float(s.median_price_per_sqm) for s in snaps)
            real = sum(s.real_listing_count for s in snaps)
            synthetic = sum(s.synthetic_listing_count for s in snaps)
            growth = [(float(s.forecast_12m) / float(s.median_price_per_sqm) - 1) * 100
                      for s in snaps if s.forecast_12m and s.median_price_per_sqm]
            trend_pct = median(growth) if growth else 0.0
            sale_prices = [float(s.median_sale_price) for s in snaps if s.median_sale_price]
            snapshot_date = max(s.as_of_date for s in snaps)
            age_days = (date.today() - snapshot_date).days
            freshness = 'FRESH' if age_days < 7 else 'ACCEPTABLE' if age_days < 30 else 'STALE'
            if freshness == 'FRESH':
                prefix = ''
            elif freshness == 'ACCEPTABLE':
                prefix = f'As of {snapshot_date}: '
            else:
                prefix = f'Note: Data from {snapshot_date} (may be outdated). '
            return {
                'available': True,
                'delegation': name,
                'median_price_per_sqm': ppm,
                'median_price_total': median(sale_prices) if sale_prices else 0,
                'listing_count': real,
                'listing_count_valid': real > 0,
                'synthetic_listing_count': synthetic,
                'data_basis': 'listings' if not synthetic else ('benchmarks' if not real else 'mixed'),
                'impossible_state': False,
                'supply_pressure': snaps[0].supply_pressure if len(snaps) == 1 else 'unknown',
                'trend_direction': 'rising' if trend_pct > 0.5 else ('falling' if trend_pct < -0.5 else 'stable'),
                'trend_pct': round(trend_pct, 1),
                'as_of_date': str(snapshot_date),
                'age_days': age_days,
                'freshness': freshness,
                'source_tag': f'market_snapshot_{snapshot_date}',
                'freshness_prefix': prefix,
            }
        except Exception as e:
            logger.warning(f'Market snapshot retrieval failed for {location}: {e}', exc_info=True)
            return {
                'available': False,
                'reason': 'Market data is temporarily unavailable.',
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
            
            from estatemind.intelligence.forecast.services.forecast_service import get_governorate_forecast_summary

            delegation, region = self._resolve_location(location)
            if delegation is not None:
                forecast = get_delegation_forecast(delegation_name=delegation.name, property_type=property_type)
            elif region is not None:  # a governorate name: its delegations' average
                forecast = get_governorate_forecast_summary(region.governorate, property_type)
            else:
                forecast = None
            
            if forecast and forecast.get('summary'):
                summary = forecast['summary']
                # the summary keys are growth_pct_12m / trend; reading price_change_pct and
                # confidence returned 0.0% and an invented 50% confidence for every place
                return {
                    'available': True,
                    'price_change_12m_pct': summary.get('growth_pct_12m', 0),
                    'trend_direction': summary.get('trend', 'stable'),
                    'confidence': None,  # the forecast summary carries no confidence
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
            logger.warning(f'Forecast retrieval failed for {location}: {e}', exc_info=True)
            return {
                'available': False,
                'reason': 'Forecast data is temporarily unavailable.'
            }
    
    def _get_climate_risk(self, location: str) -> Dict:
        """Climate score of a delegation, or the average over a governorate's delegations.
        (A substring match on delegation names answered 'Sousse' with Hammam Sousse.)"""
        try:
            from statistics import mean

            from estatemind.market.core.models import DelegationClimateScore

            delegation, region = self._resolve_location(location)
            if delegation is not None:
                scores = list(DelegationClimateScore.objects.filter(delegation=delegation))
                name = delegation.name
            elif region is not None:
                scores = list(DelegationClimateScore.objects.filter(delegation__region=region))
                name = region.governorate
            else:
                return {'available': False, 'reason': f'I could not find a place called "{location}".'}
            if not scores:
                return {'available': False, 'reason': f'No climate score available for {name}'}

            avg = lambda field: round(mean(getattr(x, field) for x in scores), 2)  # noqa: E731
            composite = avg('composite_score')
            from estatemind.intelligence.climate.services.composite_scorer import ClimateCompositeScorer
            label = ClimateCompositeScorer()._score_to_label(composite)
            latest = max(x.computed_at for x in scores)
            return {
                'available': True,
                'delegation': name,
                'delegation_count': len(scores),
                'composite_score': composite,
                'risk_label': label,
                'flood_risk': avg('flood_risk_score'),
                'heat_stress': avg('heat_stress_score'),
                'water_stress': avg('water_stress_score'),
                'coastal_erosion': avg('coastal_erosion_score'),
                'infrastructure_resilience': avg('infrastructure_resilience_score'),
                'wildfire_risk': avg('wildfire_risk_score'),
                'computed_at': latest.isoformat(),
                'source_tag': f'climate_score_{latest.date()}',
            }
        except Exception as e:
            logger.warning(f'Climate risk retrieval failed for {location}: {e}', exc_info=True)
            return {'available': False, 'reason': 'Climate data is temporarily unavailable.'}

    def _get_investment_context(self, location: str) -> Dict:
        """Rule-based opportunity score (the same scoring as the investor opportunities
        list) at the place's current median price per m2. (This used to read a
        hard-coded table of grades for six cities.)"""
        try:
            from estatemind.intelligence.investor.services.delegation_scoring import score_delegation

            market = self._get_market_snapshot(location, 'delegation')
            if not market.get('available'):
                return {'available': False, 'reason': market.get('reason', '')}
            delegation, region = self._resolve_location(location)
            scored = score_delegation(delegation.name if delegation else '',
                                      region.governorate if region else '', market['median_price_per_sqm'])
            if not scored:
                return {'available': False, 'reason': f'No investment analysis available for {location}'}
            return {
                'available': True,
                'delegation': market['delegation'],
                'grade': scored['investment_grade'],
                'opportunity_score': scored['opportunity_score'],
                'risk_level': 'unknown',
                'rental_yield_potential': scored['gross_yield_pct'],
                'capital_appreciation': scored['forecast_12m_pct'],
                'scoring_method': 'rule_based',
                'source_tag': 'investment_analysis',
                'analyzed_at': timezone.now().isoformat()
            }
        except Exception as e:
            logger.warning(f'Investment analysis failed for {location}: {e}', exc_info=True)
            return {
                'available': False,
                'reason': 'Investment analysis is temporarily unavailable.'
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
                top_investments = self._get_investment_rankings(property_type)
                context['investment'] = top_investments
                if not top_investments.get('available'):
                    retrieval_errors.append(top_investments.get('reason', 'Unknown error'))
        
        except Exception as e:
            logger.error(f'National rankings retrieval failed: {e}', exc_info=True)
            retrieval_errors.append('Rankings are temporarily unavailable.')
        
        return {
            'context': context,
            'retrieval_errors': retrieval_errors,
            'is_fully_grounded': len(retrieval_errors) == 0,
            'retrieved_at': timezone.now().isoformat(),
            'location': 'NATIONWIDE',
            'location_type': 'national'
        }
    
    @staticmethod
    def _real_medians(property_type: str) -> list[dict]:
        """Median sale price per m2 of real (not sample) listings of one property type,
        per delegation with at least MIN_REAL_LISTINGS of them. One type at a time:
        mixing land with apartments made land-heavy delegations look cheapest."""
        from statistics import median

        from estatemind.market.core.models import SYNTHETIC_SOURCE, Property

        groups: dict[int, dict] = {}
        rows = (Property.objects.filter(is_active=True, transaction_type='sale', property_type=property_type,
                                        delegation__isnull=False, price__gt=0, area_sqm__gt=0)
                .exclude(source=SYNTHETIC_SOURCE).exclude(price_imputed=True).exclude(area_imputed=True)
                .values_list('delegation_id', 'delegation__name', 'delegation__region__governorate',
                             'price', 'area_sqm'))
        for delegation_id, name, governorate, price, area in rows:
            g = groups.setdefault(delegation_id, {'delegation': name, 'governorate': governorate, 'ppm': []})
            g['ppm'].append(price / area)
        return [{'delegation': g['delegation'], 'governorate': g['governorate'],
                 'median_price_per_sqm': median(g['ppm']), 'listing_count': len(g['ppm'])}
                for g in groups.values() if len(g['ppm']) >= MIN_REAL_LISTINGS]

    def _get_market_rankings(self, property_type: str) -> Dict:
        """Most expensive and cheapest delegations by the median price per m2 of real
        sale listings of the asked property type. (This read a DelegationStats model
        that doesn't exist, so it always reported rankings as unavailable.)"""
        try:
            medians = self._real_medians(property_type)
            if not medians:
                return {'available': False, 'reason': f'Not enough real {property_type} listings to rank delegations'}

            def row(rank, m):
                return {'rank': rank, 'delegation': m['delegation'], 'governorate': m['governorate'],
                        'median_price_per_sqm': round(m['median_price_per_sqm']),
                        'listing_count': m['listing_count']}

            by_price = sorted(medians, key=lambda m: m['median_price_per_sqm'], reverse=True)
            return {
                'available': True,
                'ranking_type': 'median_price_per_m2',
                'top_delegations': [row(i + 1, m) for i, m in enumerate(by_price[:10])],
                'cheapest_delegations': [row(i + 1, m) for i, m in enumerate(by_price[::-1][:10])],
                'ranked_count': len(medians),
                'min_real_listings': MIN_REAL_LISTINGS,
                'property_type': property_type,
                'source_tag': 'market_rankings',
                'retrieved_at': timezone.now().isoformat()
            }
        except Exception as e:
            logger.warning(f'Market rankings failed: {e}', exc_info=True)
            return {'available': False, 'reason': 'Market rankings are temporarily unavailable.'}

    def _get_forecast_rankings(self, property_type: str) -> Dict:
        """Top 10 delegations by forecast growth over 12 months, measured within each
        delegation's latest forecast (first month to last), as the per-place answers
        and the forecast pages do. (This divided the forecast level by current listing
        prices; forecast levels sit well below listing prices, so every delegation
        showed a large fall.)"""
        try:
            from estatemind.intelligence.forecast.models import DelegationForecast

            series = {}
            for f in (DelegationForecast.objects.filter(property_type=property_type)
                      .order_by('delegation_name', 'forecast_origin', 'horizon_idx')):
                key = f.delegation_name
                if key not in series or f.forecast_origin > series[key]['origin']:
                    series[key] = {'origin': f.forecast_origin, 'governorate': f.governorate, 'points': {}}
                if f.forecast_origin == series[key]['origin']:
                    series[key]['points'][f.horizon_idx] = f.predicted_price_per_m2

            rankings = []
            for name, info in series.items():
                points = info['points']
                first, last = points.get(min(points)), points.get(max(points))
                if len(points) < 2 or not first or first <= 0 or not last:
                    continue
                rankings.append({
                    'delegation': name,
                    'governorate': info['governorate'],
                    'growth_pct_12m': round((last - first) / first * 100, 2),
                })

            if not rankings:
                return {'available': False, 'reason': 'No forecast ranking data available'}

            rankings.sort(key=lambda x: x['growth_pct_12m'], reverse=True)
            top_rankings = rankings[:10]
            for i, r in enumerate(top_rankings):
                r['rank'] = i + 1
            return {
                'available': True,
                'ranking_type': 'fastest_growing_12m',
                'top_delegations': top_rankings,
                'ranked_count': len(rankings),
                'property_type': property_type,
                'source_tag': 'forecast_rankings',
                'retrieved_at': timezone.now().isoformat()
            }
        except Exception as e:
            logger.warning(f'Forecast rankings failed: {e}', exc_info=True)
            return {'available': False, 'reason': 'Forecast rankings are temporarily unavailable.'}

    def _get_investment_rankings(self, property_type: str = 'apartment') -> Dict:
        """Top 10 delegations by the rule-based opportunity score (the same scoring as
        the per-place answers and the investor opportunities list), at each
        delegation's median price per m2. Delegations need MIN_REAL_LISTINGS real
        listings of the asked type. (Zone ranking used to be reported as not implemented.)"""
        try:
            from estatemind.intelligence.investor.services.delegation_scoring import score_delegation

            scored = []
            for m in self._real_medians(property_type):
                result = score_delegation(m['delegation'], m['governorate'], m['median_price_per_sqm'],
                                          property_type=property_type)
                if result:
                    scored.append(result)
            if not scored:
                return {'available': False, 'reason': 'No investment ranking data available'}
            scored.sort(key=lambda r: r['opportunity_score'], reverse=True)
            top = [{'rank': i + 1, 'delegation': r['delegation'], 'governorate': r['governorate'],
                    'opportunity_score': r['opportunity_score'], 'grade': r['investment_grade'],
                    'gross_yield_pct': r['gross_yield_pct']}
                   for i, r in enumerate(scored[:10])]
            return {
                'available': True,
                'ranking_type': 'best_investment_opportunities',
                'property_type': property_type,
                'top_delegations': top,
                'ranked_count': len(scored),
                'scoring_method': 'rule_based',
                'source_tag': 'investment_rankings',
                'retrieved_at': timezone.now().isoformat()
            }
        except Exception as e:
            logger.warning(f'Investment rankings failed: {e}', exc_info=True)
            return {'available': False, 'reason': 'Investment rankings are temporarily unavailable.'}
