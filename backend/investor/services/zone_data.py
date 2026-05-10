"""
Loads investor zone_market_stats.csv and zone_price_forecasts.csv once,
returns zone-level features for a given (delegation, property_type).
"""
from pathlib import Path
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[4]
_ZONE_STATS_CSV   = _ROOT / 'investor' / 'data' / 'zone_market_stats.csv'
_ZONE_FCST_CSV    = _ROOT / 'investor' / 'data' / 'zone_price_forecasts.csv'
_MACRO_CSV        = _ROOT / 'investor' / 'data' / 'macro_indicators.csv'

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


def get_zone_forecast(delegation: str, property_type: str) -> dict:
    """Return forecast features for a delegation + property_type."""
    ptype_norm = _PTYPE_NORM.get(property_type.lower(), 'Apartment').lower()
    deleg_key  = delegation.lower().strip()

    defaults = {
        'forecast_3m_pct':          2.0,
        'forecast_6m_pct':          3.5,
        'forecast_12m_pct':         6.0,
        'forecast_direction':       'UP',
        'forecast_direction_code':  1.0,
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

    return defaults


def _isnan(v):
    try:
        import math
        return math.isnan(float(v))
    except Exception:
        return True
