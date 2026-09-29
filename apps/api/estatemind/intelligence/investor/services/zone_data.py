"""
Loads investor zone_market_stats.csv and zone_price_forecasts.csv once,
returns zone-level features for a given (delegation, property_type).
"""
from pathlib import Path
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

_DATA = Path(__file__).resolve().parents[1] / 'data'  # investor/data/
_ZONE_STATS_CSV   = _DATA / 'zone_market_stats.csv'
_ZONE_FCST_CSV    = _DATA / 'zone_price_forecasts.csv'
_MACRO_CSV        = _DATA / 'macro_indicators.csv'

_PTYPE_NORM = {
    'apartment': 'Apartment', 'house': 'House', 'villa': 'House',
    'commercial': 'Commercial', 'office': 'Commercial',
    'land': 'Land', 'farm': 'Land',
}

# Latest macro defaults (2026 calibration)
MACRO = {
    'bct_benchmark_rate_pct':        7.75,
    'inflation_rate_cpi_pct':        8.8,
    'eur_tnd_rate':                  3.35,
    'usd_tnd_rate':                  3.10,
    'construction_cost_index':       110.0,
    'gdp_growth_rate_q_pct':         1.2,
    'avg_mortgage_rate_pct':         10.0,
    'unemployment_rate_national_pct':16.0,
    'unemployment_rate_tunis_pct':   12.0,
    'unemployment_rate_sfax_pct':    14.0,
    'unemployment_rate_sousse_pct':  13.0,
    'unemployment_rate_interior_pct':25.0,
    'real_estate_credit_growth_pct': 2.5,
}


@lru_cache(maxsize=1)
def _load_zone_stats():
    try:
        import pandas as pd
        df = pd.read_csv(_ZONE_STATS_CSV)
        df['delegation_lower'] = df['delegation'].str.lower().str.strip()
        df['ptype_lower']      = df['property_type'].str.lower().str.strip()
        # Keep most recent snapshot per zone
        df = df.sort_values('snapshot_date').groupby(
            ['delegation_lower', 'ptype_lower'], as_index=False
        ).last()
        return df
    except Exception as e:
        logger.warning("Could not load zone_market_stats.csv: %s", e)
        return None


@lru_cache(maxsize=1)
def _load_zone_forecasts():
    try:
        import pandas as pd
        df = pd.read_csv(_ZONE_FCST_CSV)
        df['delegation_lower'] = df['delegation'].str.lower().str.strip()
        df['ptype_lower']      = df['property_type'].str.lower().str.strip()
        df = df.sort_values('forecast_generated_date').groupby(
            ['delegation_lower', 'ptype_lower'], as_index=False
        ).last()
        return df
    except Exception as e:
        logger.warning("Could not load zone_price_forecasts.csv: %s", e)
        return None


def get_zone_stats(delegation: str, property_type: str) -> dict:
    """Return zone stats dict for a delegation + property_type."""
    ptype_norm = _PTYPE_NORM.get(property_type.lower(), 'Apartment').lower()
    deleg_key  = delegation.lower().strip()

    defaults = {
        'demand_intensity_score':    60.0,
        'supply_demand_ratio':       1.0,
        'median_days_on_market':     45.0,
        'vacancy_rate_pct':          7.0,
        'avg_proximity_school_km':   1.5,
        'avg_proximity_hospital_km': 3.0,
        'avg_proximity_transport_km':1.0,
        'price_change_mom_pct':      0.5,
        'price_change_yoy_pct':      6.0,
        'zone_population':           80000.0,
        'transaction_velocity_score':50.0,
        'avg_price_per_m2_tnd':      1500.0,
        'median_price_per_m2_tnd':   1400.0,
    }

    df = _load_zone_stats()
    if df is not None:
        row = df[(df['delegation_lower'] == deleg_key) & (df['ptype_lower'] == ptype_norm)]
        if row.empty:
            row = df[df['delegation_lower'] == deleg_key]
        if not row.empty:
            r = row.iloc[0]
            for k in defaults:
                if k in r.index and not _isnan(r[k]):
                    defaults[k] = float(r[k])

    return defaults


def forecast_outlook(delegation: str, property_type: str) -> dict:
    """12-month price outlook for a delegation, from the forecast module (the same
    forecast the forecast pages, the chatbot and valuations use).

    growth_*_pct are within the forecast series (first month to month 6 / 12);
    low/high_12m_pct come from the forecast's 12th-month interval, which is an
    unmeasured illustrative band (no price history exists to calibrate it).
    Without a forecast, available is False and the figures are None: no growth is
    invented. (The investor pages used to read a static CSV and fall back to
    +3.5% / +6.0% 'UP'.)"""
    none = {'available': False, 'source': None, 'growth_6m_pct': None, 'growth_12m_pct': None,
            'low_12m_pct': None, 'high_12m_pct': None, 'direction': None}
    if not delegation:
        return none
    try:
        from estatemind.intelligence.forecast.services.forecast_service import get_delegation_forecast

        ptype = _PTYPE_NORM.get(str(property_type).lower(), 'Apartment').lower()
        ptype = 'house' if ptype == 'house' else 'land' if ptype == 'land' else 'apartment'
        forecast = get_delegation_forecast(delegation_name=delegation, property_type=ptype)
    except Exception as e:  # no forecast tables yet, bad name...
        logger.info('No forecast for %s/%s: %s', delegation, property_type, e)
        forecast = None
    summary = (forecast or {}).get('summary') or {}
    g12 = summary.get('growth_pct_12m')
    if g12 is None:
        return none
    current = summary.get('current_price_per_m2') or 0
    last = ((forecast or {}).get('months') or [{}])[-1]
    low = high = g12
    if current and last.get('lower') and last.get('upper'):
        low = round((last['lower'] / current - 1) * 100, 2)
        high = round((last['upper'] / current - 1) * 100, 2)
    return {
        'available': True, 'source': 'forecast_module',
        'growth_6m_pct': summary.get('growth_pct_6m'), 'growth_12m_pct': g12,
        'low_12m_pct': min(low, g12), 'high_12m_pct': max(high, g12),
        'direction': 'UP' if g12 > 0.5 else 'DOWN' if g12 < -0.5 else 'FLAT',
    }


def real_zone_stats(delegation: str, property_type: str) -> dict:
    """What the listings actually show for a delegation: counts of real (not
    sample) sale and rent listings of the type, and their median sale price per
    m2. (The zone stats CSV holds one constant value per column for every
    delegation: demand 60, vacancy 7%, 45 days on market...)"""
    from statistics import median

    from estatemind.market.core.models import SYNTHETIC_SOURCE, Property

    ptype = _PTYPE_NORM.get(str(property_type).lower(), 'Apartment').lower()
    ptype = 'house' if ptype == 'house' else 'land' if ptype == 'land' else 'apartment'
    rows = (Property.objects.filter(is_active=True, property_type=ptype, delegation__name__iexact=delegation,
                                    price__gt=0, area_sqm__gt=0)
            .exclude(source=SYNTHETIC_SOURCE).values_list('transaction_type', 'price', 'area_sqm'))
    sale = [p / a for t, p, a in rows if t == 'sale']
    return {
        'sale_listing_count': len(sale),
        'rent_listing_count': sum(1 for t, _, _ in rows if t == 'rent'),
        'median_sale_price_per_m2': round(median(sale)) if sale else None,
    }


def get_zone_forecast(delegation: str, property_type: str) -> dict:
    """Forecast features for a delegation + property_type: the forecast module
    first (forecast_outlook), then the benchmark trend CSV, else neutral (0%,
    FLAT) with forecast_available False. Models take numbers, so a missing
    forecast is 0 growth here; display code must use forecast_available."""
    ptype_norm = _PTYPE_NORM.get(property_type.lower(), 'Apartment').lower()
    deleg_key  = delegation.lower().strip()

    defaults = {
        'forecast_available':       False,
        'forecast_source':          None,
        'forecast_3m_pct':          0.0,
        'forecast_6m_pct':          0.0,
        'forecast_12m_pct':         0.0,
        'forecast_12m_low_pct':     None,
        'forecast_12m_high_pct':    None,
        'forecast_direction':       'FLAT',
        'forecast_direction_code':  0.0,
        'forecast_confidence':      'medium',
        'forecast_confidence_code': 1.0,
        'trend_volatility_score':   25.0,
        'forecast_reliability':     0.6,
        'forecast_reliability_score':60.0,
        'forecast_momentum':        1.0,
    }

    df = _load_zone_forecasts()
    if df is not None:
        row = df[(df['delegation_lower'] == deleg_key) & (df['ptype_lower'] == ptype_norm)]
        if row.empty:
            row = df[df['delegation_lower'] == deleg_key]
        if not row.empty:
            r = row.iloc[0]
            for k in ['forecast_3m_pct', 'forecast_6m_pct', 'forecast_12m_pct',
                      'trend_volatility_score', 'forecast_reliability']:
                if k in r.index and not _isnan(r[k]):
                    defaults[k] = float(r[k])
            if 'forecast_direction' in r.index:
                d = str(r['forecast_direction']).upper()
                defaults['forecast_direction']      = d
                defaults['forecast_direction_code'] = 1.0 if d == 'UP' else (-1.0 if d == 'DOWN' else 0.0)
            if 'forecast_confidence' in r.index:
                c = str(r['forecast_confidence']).lower()
                defaults['forecast_confidence']      = c
                defaults['forecast_confidence_code'] = 2.0 if c == 'high' else (1.0 if c == 'medium' else 0.0)
            defaults['forecast_reliability_score'] = defaults['forecast_reliability'] * 100
            defaults['forecast_momentum'] = defaults['forecast_6m_pct'] / max(abs(defaults['forecast_3m_pct']), 0.01)
            defaults['forecast_available'] = True
            defaults['forecast_source'] = 'benchmark_trend'

    outlook = forecast_outlook(delegation, property_type)
    if outlook['available']:
        g6, g12 = outlook['growth_6m_pct'] or 0.0, outlook['growth_12m_pct']
        defaults.update({
            'forecast_available': True, 'forecast_source': outlook['source'],
            'forecast_3m_pct': g6 / 2, 'forecast_6m_pct': g6, 'forecast_12m_pct': g12,
            'forecast_12m_low_pct': outlook['low_12m_pct'], 'forecast_12m_high_pct': outlook['high_12m_pct'],
            'forecast_direction': outlook['direction'],
            'forecast_direction_code': {'UP': 1.0, 'DOWN': -1.0}.get(outlook['direction'], 0.0),
            'forecast_momentum': g6 / max(abs(g6 / 2), 0.01),
        })
    elif defaults['forecast_available']:
        base = defaults['forecast_12m_pct']
        defaults['forecast_12m_low_pct'] = defaults['forecast_12m_high_pct'] = base
    return defaults


def _isnan(v):
    try:
        import math
        return math.isnan(float(v))
    except Exception:
        return True
