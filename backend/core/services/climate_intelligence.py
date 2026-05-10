"""
core/services/climate_intelligence.py

Climate Intelligence Engine — ported from the standalone ClimaTN Flask app.

Responsibilities:
  1. Static risk data for all 24 Tunisian governorates
  2. compute_risk_score()   — weighted composite risk 0-10 + category
  3. compute_sustainability() — stability/water/thermal/coastal formula → 0-100 + grade
  4. climate_price_adjustment() — property-type-aware price delta percentage
  5. fetch_live_weather()   — Open-Meteo real-time weather + live risk indices
  6. flood_index()          — baseline + real-time precipitation
  7. heat_index_level()     — Rotherford formula → Safe/Caution/Danger/Extreme
  8. drought_spi()          — Standardized Precipitation Index

Results from fetch_live_weather() are cached for 5 minutes (Django cache).
"""

import math
import logging
from typing import Optional

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ─── Open-Meteo endpoints (free, no API key) ──────────────────────────────────
_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
_ARCHIVE_URL  = 'https://archive-api.open-meteo.com/v1/archive'
_WEATHER_CACHE_TTL = 300  # 5 minutes

# ─── All 24 Tunisian governorates — coordinates + coastal flag + climate region
# Ported from CITIES dict in app.py
GOVERNORATE_META: dict[str, dict] = {
    'Tunis':       {'lat': 36.82, 'lon': 10.17, 'region': 'North',        'coastal': True},
    'Sfax':        {'lat': 34.74, 'lon': 10.76, 'region': 'Center-East',  'coastal': True},
    'Sousse':      {'lat': 35.83, 'lon': 10.64, 'region': 'Center-East',  'coastal': True},
    'Kairouan':    {'lat': 35.68, 'lon':  9.11, 'region': 'Center',       'coastal': False},
    'Bizerte':     {'lat': 37.27, 'lon':  9.87, 'region': 'North',        'coastal': True},
    'Gabes':       {'lat': 33.88, 'lon':  9.90, 'region': 'South-East',   'coastal': True},
    'Ariana':      {'lat': 36.86, 'lon': 10.19, 'region': 'North',        'coastal': False},
    'Gafsa':       {'lat': 34.43, 'lon':  8.78, 'region': 'South-West',   'coastal': False},
    'Monastir':    {'lat': 35.77, 'lon': 10.83, 'region': 'Center-East',  'coastal': True},
    'Nabeul':      {'lat': 36.45, 'lon': 10.73, 'region': 'North-East',   'coastal': True},
    'Beja':        {'lat': 36.73, 'lon':  9.18, 'region': 'North-West',   'coastal': False},
    'Jendouba':    {'lat': 36.50, 'lon':  8.78, 'region': 'North-West',   'coastal': False},
    'Tozeur':      {'lat': 33.92, 'lon':  8.13, 'region': 'South-West',   'coastal': False},
    'Medenine':    {'lat': 33.35, 'lon': 10.50, 'region': 'South',        'coastal': False},
    'Tataouine':   {'lat': 32.93, 'lon': 10.45, 'region': 'South',        'coastal': False},
    'Kasserine':   {'lat': 35.17, 'lon':  8.83, 'region': 'Center-West',  'coastal': False},
    'Sidi Bouzid': {'lat': 35.04, 'lon':  9.49, 'region': 'Center',       'coastal': False},
    'Mahdia':      {'lat': 35.50, 'lon': 11.06, 'region': 'Center-East',  'coastal': True},
    'Zaghouan':    {'lat': 36.40, 'lon': 10.14, 'region': 'North',        'coastal': False},
    'Kebili':      {'lat': 33.70, 'lon':  8.97, 'region': 'South',        'coastal': False},
    'Ben Arous':   {'lat': 36.75, 'lon': 10.22, 'region': 'North',        'coastal': False},
    'Siliana':     {'lat': 36.08, 'lon':  9.37, 'region': 'North-West',   'coastal': False},
    'Kef':         {'lat': 36.18, 'lon':  8.71, 'region': 'North-West',   'coastal': False},
    'Manouba':     {'lat': 36.81, 'lon': 10.10, 'region': 'North',        'coastal': False},
}

# ─── Per-governorate risk levels (from tunisia_climate_risk_dataset.csv) ──────
# Keys: flood, heat, drought, earthquake  — values: Low/Medium/High/Very High
GOVERNORATE_RISK: dict[str, dict] = {
    'Tunis':       {'flood': 'High',   'heat': 'High',      'drought': 'Medium', 'earthquake': 'Low'},
    'Sfax':        {'flood': 'Medium', 'heat': 'High',      'drought': 'High',   'earthquake': 'Low'},
    'Sousse':      {'flood': 'Medium', 'heat': 'High',      'drought': 'Medium', 'earthquake': 'Low'},
    'Kairouan':    {'flood': 'Medium', 'heat': 'Very High', 'drought': 'High',   'earthquake': 'Low'},
    'Bizerte':     {'flood': 'Medium', 'heat': 'Medium',    'drought': 'Low',    'earthquake': 'Low'},
    'Gabes':       {'flood': 'High',   'heat': 'High',      'drought': 'High',   'earthquake': 'Low'},
    'Ariana':      {'flood': 'High',   'heat': 'High',      'drought': 'Medium', 'earthquake': 'Low'},
    'Gafsa':       {'flood': 'Low',    'heat': 'Very High', 'drought': 'High',   'earthquake': 'Medium'},
    'Monastir':    {'flood': 'Low',    'heat': 'High',      'drought': 'Medium', 'earthquake': 'Low'},
    'Nabeul':      {'flood': 'Medium', 'heat': 'High',      'drought': 'Low',    'earthquake': 'Low'},
    'Beja':        {'flood': 'Medium', 'heat': 'Medium',    'drought': 'Low',    'earthquake': 'Low'},
    'Jendouba':    {'flood': 'High',   'heat': 'Medium',    'drought': 'Low',    'earthquake': 'Low'},
    'Tozeur':      {'flood': 'Low',    'heat': 'Very High', 'drought': 'Very High', 'earthquake': 'Low'},
    'Medenine':    {'flood': 'Low',    'heat': 'High',      'drought': 'High',   'earthquake': 'Low'},
    'Tataouine':   {'flood': 'Low',    'heat': 'High',      'drought': 'High',   'earthquake': 'Low'},
    'Kasserine':   {'flood': 'Medium', 'heat': 'High',      'drought': 'High',   'earthquake': 'Low'},
    'Sidi Bouzid': {'flood': 'Medium', 'heat': 'High',      'drought': 'High',   'earthquake': 'Low'},
    'Mahdia':      {'flood': 'Low',    'heat': 'High',      'drought': 'Medium', 'earthquake': 'Low'},
    'Zaghouan':    {'flood': 'Medium', 'heat': 'Medium',    'drought': 'Medium', 'earthquake': 'Low'},
    'Kebili':      {'flood': 'Low',    'heat': 'Very High', 'drought': 'Very High', 'earthquake': 'Low'},
    'Ben Arous':   {'flood': 'High',   'heat': 'High',      'drought': 'Medium', 'earthquake': 'Low'},
    'Siliana':     {'flood': 'Medium', 'heat': 'Medium',    'drought': 'Medium', 'earthquake': 'Low'},
    'Kef':         {'flood': 'Medium', 'heat': 'Medium',    'drought': 'Low',    'earthquake': 'Low'},
    'Manouba':     {'flood': 'High',   'heat': 'High',      'drought': 'Medium', 'earthquake': 'Low'},
}

# ─── Climate variables per governorate (rainfall mm/year, hot days >35°C/year) ─
GOVERNORATE_CLIMATE_VARS: dict[str, dict] = {
    'Tunis':       {'rain_mm': 521,  'hot_days': 77},
    'Sfax':        {'rain_mm': 298,  'hot_days': 74},
    'Sousse':      {'rain_mm': 347,  'hot_days': 81},
    'Kairouan':    {'rain_mm': 277,  'hot_days': 85},
    'Bizerte':     {'rain_mm': 627,  'hot_days': 45},
    'Gabes':       {'rain_mm': 192,  'hot_days': 90},
    'Ariana':      {'rain_mm': 490,  'hot_days': 75},
    'Gafsa':       {'rain_mm': 163,  'hot_days': 110},
    'Monastir':    {'rain_mm': 325,  'hot_days': 78},
    'Nabeul':      {'rain_mm': 445,  'hot_days': 65},
    'Beja':        {'rain_mm': 622,  'hot_days': 55},
    'Jendouba':    {'rain_mm': 650,  'hot_days': 60},
    'Tozeur':      {'rain_mm':  83,  'hot_days': 140},
    'Medenine':    {'rain_mm': 180,  'hot_days': 95},
    'Tataouine':   {'rain_mm': 105,  'hot_days': 100},
    'Kasserine':   {'rain_mm': 348,  'hot_days': 85},
    'Sidi Bouzid': {'rain_mm': 287,  'hot_days': 90},
    'Mahdia':      {'rain_mm': 310,  'hot_days': 75},
    'Zaghouan':    {'rain_mm': 450,  'hot_days': 70},
    'Kebili':      {'rain_mm':  95,  'hot_days': 130},
    'Ben Arous':   {'rain_mm': 480,  'hot_days': 76},
    'Siliana':     {'rain_mm': 410,  'hot_days': 70},
    'Kef':         {'rain_mm': 490,  'hot_days': 60},
    'Manouba':     {'rain_mm': 460,  'hot_days': 76},
}

# ─── Risk level → numeric value mapping ───────────────────────────────────────
_RISK_NUM: dict[str, float] = {
    'Low': 1.0, 'Medium': 3.0, 'High': 7.0, 'Very High': 10.0,
}


# ─────────────────────────────────────────────────────────────────────────────
# Core algorithms
# ─────────────────────────────────────────────────────────────────────────────

def compute_risk_score(governorate: str) -> tuple[float, str]:
    """
    Weighted composite risk score (0–10) for a governorate.
    Weights: flood 30%, heat 30%, drought 25%, earthquake 15%.
    Returns (score, category) where category is Low/Moderate/High/Very High.
    """
    r = GOVERNORATE_RISK.get(governorate, {'flood': 'Medium', 'heat': 'High', 'drought': 'Medium', 'earthquake': 'Low'})
    score = round(
        _RISK_NUM.get(r['flood'],      3.0) * 0.30
        + _RISK_NUM.get(r['heat'],     3.0) * 0.30
        + _RISK_NUM.get(r['drought'],  3.0) * 0.25
        + _RISK_NUM.get(r['earthquake'], 1.0) * 0.15,
        2,
    )
    if score <= 3.0:   category = 'Low'
    elif score <= 5.0: category = 'Moderate'
    elif score <= 7.5: category = 'High'
    else:              category = 'Very High'
    return score, category


def compute_sustainability(governorate: str) -> tuple[float, str]:
    """
    Sustainability score (0–100) and grade (A–F).
    Formula: stability×40% + water×25% + thermal×20% + coastal_factor×15%
    """
    info = GOVERNORATE_META.get(governorate, {})
    cv   = GOVERNORATE_CLIMATE_VARS.get(governorate, {'rain_mm': 300, 'hot_days': 80})
    r    = GOVERNORATE_RISK.get(governorate, {})
    rs, _ = compute_risk_score(governorate)

    stability = (10 - rs) / 10
    water     = min(cv['rain_mm'] / 600, 1.0)
    thermal   = max(0.0, 1.0 - cv['hot_days'] / 150)
    flood_lv  = r.get('flood', 'Medium')
    sea_pen   = {'High': 0.40, 'Very High': 0.25, 'Medium': 0.65, 'Low': 0.90}.get(flood_lv, 0.70)
    coastal   = sea_pen if info.get('coastal', False) else 0.85

    raw   = stability * 0.40 + water * 0.25 + thermal * 0.20 + coastal * 0.15
    score = round(raw * 100, 1)
    grade = 'A' if score >= 75 else 'B' if score >= 60 else 'C' if score >= 45 else 'D' if score >= 30 else 'F'
    return score, grade


def climate_price_adjustment(
    governorate: str,
    property_type: str = 'apartment',
    risk_category: Optional[str] = None,
) -> tuple[float, str]:
    """
    Climate-driven property price adjustment.
    Returns (adjustment_pct, label) where adjustment_pct is e.g. -8.5 or +3.5.
    Mirrors the climate_price_adjustment() function from app.py.
    """
    r = GOVERNORATE_RISK.get(governorate, {})
    if risk_category is None:
        _, risk_category = compute_risk_score(governorate)

    category_adj = {'Low': 0.035, 'Moderate': 0.0, 'High': -0.085, 'Very High': -0.16}.get(risk_category, 0.0)
    flood_adj    = {'Low': 0.008, 'Medium': 0.0, 'High': -0.020, 'Very High': -0.040}.get(r.get('flood', 'Medium'), 0.0)
    heat_adj     = {'Low': 0.004, 'Medium': 0.0, 'High': -0.012, 'Very High': -0.024}.get(r.get('heat', 'Medium'), 0.0)
    drought_adj  = {'Low': 0.004, 'Medium': 0.0, 'High': -0.016, 'Very High': -0.030}.get(r.get('drought', 'Medium'), 0.0)

    ptype_map = {'apartment': 0.72, 'house': 1.0, 'villa': 1.0, 'land': 1.15, 'commercial': 0.90, 'office': 0.80, 'farm': 1.15}
    exposure  = ptype_map.get(property_type.lower(), 0.85)

    meta    = GOVERNORATE_META.get(governorate, {})
    coastal = meta.get('coastal', False)
    coastal_adj = (-0.012 if coastal and r.get('flood') in {'High', 'Very High'}
                   else 0.006 if coastal and r.get('flood') == 'Low'
                   else 0.0)

    raw = (category_adj + flood_adj + heat_adj * 0.75 + drought_adj * 0.85) * exposure + coastal_adj
    adjustment = round(max(-0.28, min(0.08, raw)) * 100, 2)  # clamped to [-28%, +8%]

    if adjustment >= 3.0:    label = 'Climate premium — low-risk area'
    elif adjustment <= -12:  label = 'Strong climate discount'
    elif adjustment < 0:     label = 'Climate risk discount'
    else:                    label = 'Climate-neutral area'

    return adjustment, label


# ─────────────────────────────────────────────────────────────────────────────
# Live risk indices
# ─────────────────────────────────────────────────────────────────────────────

def heat_index_level(temp_c: float, humidity_pct: float) -> str:
    """Classify heat stress from temperature + humidity."""
    if temp_c < 27:
        return 'Safe'
    # Simplified heat index (Celsius)
    e = (humidity_pct / 100) * 6.105 * math.exp(17.27 * temp_c / (237.3 + temp_c))
    hi = temp_c + 0.33 * e - 4.0
    if hi < 27:  return 'Safe'
    if hi < 32:  return 'Caution'
    if hi < 41:  return 'Danger'
    return 'Extreme'


def flood_index(baseline_flood: str, precip_mm: float) -> dict:
    """Real-time flood index combining baseline risk + current precipitation."""
    base  = {'low': 0.10, 'medium': 0.40, 'high': 0.70, 'very_high': 0.90}.get(baseline_flood.lower(), 0.30)
    rt    = min(precip_mm / 50.0, 0.50) if precip_mm else 0.0
    index = round(min(base + rt, 1.0) * 100, 1)
    level = 'Low' if index < 30 else 'Moderate' if index < 60 else 'High'
    return {'index': index, 'level': level}


def drought_spi(precip_30d: float, expected_30d: float = 25.0) -> dict:
    """
    Simplified Standardized Precipitation Index.
    Positive = wet, negative = dry. Range approximately [-3, +3].
    """
    sigma = max(expected_30d * 0.3, 1.0)
    spi   = round((precip_30d - expected_30d) / sigma, 2)
    spi   = max(-3.0, min(3.0, spi))
    if spi >= 1.0:   level = 'Wet'
    elif spi >= 0:   level = 'Near Normal'
    elif spi >= -1:  level = 'Mildly Dry'
    elif spi >= -2:  level = 'Moderate Drought'
    else:            level = 'Severe Drought'
    return {'spi': spi, 'level': level}


# ─────────────────────────────────────────────────────────────────────────────
# Open-Meteo live weather
# ─────────────────────────────────────────────────────────────────────────────

def fetch_live_weather(governorate: str) -> Optional[dict]:
    """
    Fetch real-time weather from Open-Meteo for a governorate.
    Returns a rich dict including current conditions, 7-day forecast,
    heat/flood/drought indices. Cached for 5 minutes.
    """
    cache_key = f'climate_weather_{governorate}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    meta = GOVERNORATE_META.get(governorate)
    if not meta:
        return None

    lat, lon = meta['lat'], meta['lon']

    try:
        resp = requests.get(_FORECAST_URL, params={
            'latitude':  lat,
            'longitude': lon,
            'current':   'temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weather_code',
            'daily':     'temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code',
            'forecast_days': 7,
            'timezone': 'Africa/Tunis',
        }, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning('[ClimateWeather] Open-Meteo error for %s: %s', governorate, exc)
        return _fallback_weather(governorate)

    cur   = data.get('current', {})
    daily = data.get('daily', {})

    temp   = cur.get('temperature_2m', 22.0)
    humid  = cur.get('relative_humidity_2m', 55.0)
    precip = cur.get('precipitation', 0.0)
    wind   = cur.get('wind_speed_10m', 10.0)

    r = GOVERNORATE_RISK.get(governorate, {})
    baseline_flood = r.get('flood', 'Medium').lower()

    # 30-day precip estimated from 7-day forecast sum × (30/7)
    precip_7d_sum  = sum(daily.get('precipitation_sum', []) or [])
    precip_30d_est = precip_7d_sum * (30 / 7)
    expected_30d   = GOVERNORATE_CLIMATE_VARS.get(governorate, {}).get('rain_mm', 300) / 12

    result = {
        'governorate':    governorate,
        'climate_region': meta['region'],
        'is_coastal':     meta['coastal'],
        'coords':  {'lat': lat, 'lon': lon},
        'current': {
            'temperature_c':    round(temp, 1),
            'humidity_pct':     round(humid, 1),
            'wind_kmh':         round(wind, 1),
            'precipitation_mm': round(precip, 2),
            'weather_code':     cur.get('weather_code'),
        },
        'forecast_7d': [
            {
                'date': d,
                'max_c': mx,
                'min_c': mn,
                'rain_mm': r_,
                'weather_code': wc,
            }
            for d, mx, mn, r_, wc in zip(
                daily.get('time', []),
                daily.get('temperature_2m_max', []),
                daily.get('temperature_2m_min', []),
                daily.get('precipitation_sum', []),
                daily.get('weather_code', []),
            )
        ],
        'indices': {
            'heat':   {'level': heat_index_level(temp, humid), 'temp_c': temp, 'humidity_pct': humid},
            'flood':  flood_index(baseline_flood, precip),
            'drought': drought_spi(precip_30d_est, expected_30d),
        },
        'risk_profile': {
            'flood':      r.get('flood', 'Medium'),
            'heat':       r.get('heat', 'High'),
            'drought':    r.get('drought', 'Medium'),
            'earthquake': r.get('earthquake', 'Low'),
        },
        'source': 'open-meteo',
    }

    cache.set(cache_key, result, _WEATHER_CACHE_TTL)
    return result


def _fallback_weather(governorate: str) -> dict:
    """Rule-based seasonal estimate when Open-Meteo is unavailable."""
    import datetime
    meta = GOVERNORATE_META.get(governorate, {'lat': 36.0, 'lon': 10.0, 'region': 'North', 'coastal': False})
    cv   = GOVERNORATE_CLIMATE_VARS.get(governorate, {'rain_mm': 300, 'hot_days': 80})
    month = datetime.date.today().month
    # Rough seasonal temp estimate for Tunisia
    base_temp = 15 + 12 * math.sin((month - 3) * math.pi / 6)
    humid = 70 if meta['coastal'] else 45
    r = GOVERNORATE_RISK.get(governorate, {})
    return {
        'governorate':    governorate,
        'climate_region': meta.get('region', 'Unknown'),
        'is_coastal':     meta.get('coastal', False),
        'coords':  {'lat': meta['lat'], 'lon': meta['lon']},
        'current': {
            'temperature_c':    round(base_temp, 1),
            'humidity_pct':     humid,
            'wind_kmh':         12.0,
            'precipitation_mm': 0.0,
            'weather_code':     None,
        },
        'forecast_7d': [],
        'indices': {
            'heat':   {'level': heat_index_level(base_temp, humid), 'temp_c': base_temp, 'humidity_pct': humid},
            'flood':  flood_index(r.get('flood', 'medium').lower(), 0),
            'drought': drought_spi(cv['rain_mm'] / 12, cv['rain_mm'] / 12),
        },
        'risk_profile': {
            'flood':      r.get('flood', 'Medium'),
            'heat':       r.get('heat', 'High'),
            'drought':    r.get('drought', 'Medium'),
            'earthquake': r.get('earthquake', 'Low'),
        },
        'source': 'fallback-estimate',
    }


def get_all_governorates_summary() -> list[dict]:
    """
    Lightweight summary for all 24 governorates — used by the dashboard endpoint.
    Does NOT call the weather API; uses static risk data only.
    """
    rows = []
    for gov in GOVERNORATE_META:
        score, category = compute_risk_score(gov)
        sustain, grade  = compute_sustainability(gov)
        adj_pct, label  = climate_price_adjustment(gov)
        meta = GOVERNORATE_META[gov]
        rows.append({
            'governorate':       gov,
            'climate_region':    meta['region'],
            'is_coastal':        meta['coastal'],
            'lat':               meta['lat'],
            'lon':               meta['lon'],
            'combined_risk_score': score,
            'risk_category':     category,
            'sustainability_score': sustain,
            'sustainability_grade': grade,
            'price_adjustment_pct': adj_pct,
            'price_adjustment_label': label,
            'risks': GOVERNORATE_RISK.get(gov, {}),
        })
    return sorted(rows, key=lambda x: x['combined_risk_score'])
