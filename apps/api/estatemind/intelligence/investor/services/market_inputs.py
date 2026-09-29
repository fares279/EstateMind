"""Market inputs for the Module 7 scanner and portfolio chains, from real data.

Each value comes from the platform's own data where it exists: rent from real
rental listings, growth from the price forecast, climate from the delegation
climate score, days on market from the market snapshot. A value that has to be
assumed is listed in `assumed_inputs`, so the result says what it rests on.
(These used to be filled with fixed numbers: rent = price x 5.5%, 6% growth,
climate 0.45, 30 days on market, without saying so.)
"""
from __future__ import annotations

from .market_rent import market_rent_per_m2
from .zone_data import MACRO, forecast_outlook, real_zone_stats

NEUTRAL_CLIMATE = 0.45     # middle of the 0-1 climate scale
NEUTRAL_DOM = 45.0         # days on market; no listing-duration data exists


def climate_score(delegation: str) -> float | None:
    from estatemind.market.core.models import DelegationClimateScore

    from estatemind.intelligence.valuation.inference.location import plain

    key = plain(delegation)
    for row in DelegationClimateScore.objects.select_related('delegation').order_by('-computed_at'):
        if plain(row.delegation.name) == key:
            return float(row.composite_score)
    return None


def days_on_market(delegation: str) -> float | None:
    from estatemind.market.core.models import DelegationMarketSnapshot

    snap = (DelegationMarketSnapshot.objects.filter(delegation__name__iexact=delegation)
            .exclude(median_days_on_market__isnull=True).order_by('-as_of_date').first())
    return float(snap.median_days_on_market) if snap else None


def market_inputs(delegation: str, governorate: str, property_type: str, surface_m2: float) -> dict:
    assumed = []
    stats = real_zone_stats(delegation, property_type)
    rent_pm2, rent_basis = market_rent_per_m2(delegation, governorate, property_type)
    outlook = forecast_outlook(delegation, property_type)
    climate = climate_score(delegation)
    dom = days_on_market(delegation)
    if climate is None:
        climate = NEUTRAL_CLIMATE
        assumed.append('climate_risk_score')
    if dom is None:
        dom = NEUTRAL_DOM
        assumed.append('delegation_dom')
    if not rent_pm2:
        assumed.append('delegation_median_monthly_rent')
    if not outlook['available']:
        assumed.append('delegation_price_momentum_12m')
    return {
        'delegation_median_price_m2': stats['median_sale_price_per_m2'] or 0,
        'delegation_median_monthly_rent': (rent_pm2 or 0) * float(surface_m2 or 0),
        'rent_basis': rent_basis if rent_pm2 else None,
        'delegation_price_momentum_12m': (outlook['growth_12m_pct'] or 0.0) / 100,
        'growth_12m_pct': outlook['growth_12m_pct'],
        'growth_12m_low_pct': outlook['low_12m_pct'],
        'growth_12m_high_pct': outlook['high_12m_pct'],
        'delegation_dom': dom,
        'climate_risk_score': climate,
        'national_interest_rate': MACRO['bct_benchmark_rate_pct'],
        'assumed_inputs': assumed,
    }
