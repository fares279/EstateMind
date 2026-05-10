"""
Forecast service — query layer over DelegationForecast + DelegationPriceData.
All DelegationForecast prices stored in millimes (÷1000 → TND/m²).
DelegationPriceData prices stored directly in TND/m².
"""
from __future__ import annotations
import logging
from datetime import date

logger = logging.getLogger(__name__)

MAPE = 2.50 / 100   # model mean absolute percentage error


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tnd(millimes):
    return round(millimes / 1000, 2)


def _month_label(d):
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.strftime('%b %Y')


def _trend(growth_pct):
    if growth_pct >= 2:
        return 'rising'
    if growth_pct <= -2:
        return 'falling'
    return 'stable'


# ── Single-delegation 12-month forecast ───────────────────────────────────────

def get_delegation_forecast(delegation_name: str, property_type: str = 'apartment'):
    from forecast.models import DelegationForecast
    qs = (
        DelegationForecast.objects
        .filter(delegation_name__iexact=delegation_name, property_type=property_type)
        .order_by('horizon_idx')
    )
    rows = list(qs)
    if not rows:
        return None

    months = []
    for r in rows:
        price = _tnd(r.predicted_price_per_m2)
        months.append({
            'horizon':      r.horizon_idx,
            'month':        str(r.forecast_month),
            'month_label':  _month_label(r.forecast_month),
            'price_per_m2': price,
            'lower':        round(price * (1 - MAPE), 2),
            'upper':        round(price * (1 + MAPE), 2),
        })

    first = months[0]['price_per_m2']
    mid   = months[5]['price_per_m2'] if len(months) >= 6 else first
    last  = months[-1]['price_per_m2']
    g6    = round((mid  - first) / first * 100, 2) if first else 0
    g12   = round((last - first) / first * 100, 2) if first else 0

    price_range = _get_price_range(delegation_name, property_type)

    return {
        'delegation':      rows[0].delegation_name,
        'governorate':     rows[0].governorate,
        'property_type':   property_type,
        'forecast_origin': str(rows[0].forecast_origin),
        'model_mape_pct':  rows[0].model_mape_pct,
        'model_version':   rows[0].model_version,
        'months':          months,
        'price_range':     price_range,
        'summary': {
            'current_price_per_m2': first,
            'price_6m':             mid,
            'price_12m':            last,
            'growth_pct_6m':        g6,
            'growth_pct_12m':       g12,
            'trend':                _trend(g12),
        },
    }


def _get_price_range(delegation_name: str, property_type: str):
    from forecast.models import DelegationPriceData
    try:
        obj = DelegationPriceData.objects.get(
            delegation_name__iexact=delegation_name,
            property_type=property_type,
        )
        return {
            'min':              obj.price_min,
            'avg':              obj.price_avg,
            'max':              obj.price_max,
            'annual_trend_pct': obj.annual_trend_pct,
            'notes':            obj.notes,
        }
    except DelegationPriceData.DoesNotExist:
        return None
    except DelegationPriceData.MultipleObjectsReturned:
        obj = DelegationPriceData.objects.filter(
            delegation_name__iexact=delegation_name,
            property_type=property_type,
        ).first()
        return {
            'min':              obj.price_min,
            'avg':              obj.price_avg,
            'max':              obj.price_max,
            'annual_trend_pct': obj.annual_trend_pct,
            'notes':            obj.notes,
        } if obj else None


# ── Full market summary (all delegations, one property type) ──────────────────

def get_market_data(property_type: str = 'apartment'):
    from forecast.models import DelegationPriceData, DelegationForecast

    price_qs = list(
        DelegationPriceData.objects
        .filter(property_type=property_type)
        .order_by('governorate', 'delegation_name')
    )
    if not price_qs:
        return None

    forecast_map = {
        r['delegation_name']: r['predicted_price_per_m2']
        for r in DelegationForecast.objects
        .filter(property_type=property_type, horizon_idx=12)
        .values('delegation_name', 'predicted_price_per_m2')
    }

    delegations = []
    avgs = []

    for pd in price_qs:
        mm12       = forecast_map.get(pd.delegation_name)
        price_12m  = round(mm12 / 1000, 2) if mm12 else pd.price_avg
        growth_12m = round((price_12m - pd.price_avg) / pd.price_avg * 100, 2) if pd.price_avg else 0

        avgs.append(pd.price_avg)
        delegations.append({
            'delegation':       pd.delegation_name,
            'governorate':      pd.governorate,
            'price_min':        pd.price_min,
            'price_avg':        pd.price_avg,
            'price_max':        pd.price_max,
            'price_12m':        price_12m,
            'annual_trend_pct': pd.annual_trend_pct,
            'growth_pct_12m':   growth_12m,
            'trend':            _trend(growth_12m),
            'notes':            pd.notes,
        })

    national_avg = round(sum(avgs) / len(avgs), 0) if avgs else 0
    by_price     = sorted(delegations, key=lambda x: x['price_avg'],        reverse=True)
    by_growth    = sorted(delegations, key=lambda x: x['annual_trend_pct'], reverse=True)

    return {
        'property_type':     property_type,
        'total_delegations': len(delegations),
        'national_avg':      national_avg,
        'top_price':  {'delegation': by_price[0]['delegation'],  'governorate': by_price[0]['governorate'],  'value': by_price[0]['price_avg']}  if by_price  else None,
        'top_growth': {'delegation': by_growth[0]['delegation'], 'governorate': by_growth[0]['governorate'], 'pct':   by_growth[0]['annual_trend_pct']} if by_growth else None,
        'top_decline':{'delegation': by_growth[-1]['delegation'],'governorate': by_growth[-1]['governorate'],'pct':   by_growth[-1]['annual_trend_pct']} if by_growth else None,
        'delegations': delegations,
    }


# ── Governorate-level aggregate ───────────────────────────────────────────────

def _gov_q(governorate: str):
    from django.db.models import Q
    canonical = _canonical_gov(governorate)
    variants  = _GOV_VARIANTS.get(canonical, [canonical])
    q = Q()
    for v in variants:
        q |= Q(governorate__iexact=v)
    return q


def get_governorate_forecast_summary(governorate: str, property_type: str = 'apartment'):
    from forecast.models import DelegationForecast
    from django.db.models import Avg

    qs = DelegationForecast.objects.filter(
        _gov_q(governorate), property_type=property_type
    )
    if not qs.exists():
        return None

    monthly_avgs = (
        qs.values('horizon_idx', 'forecast_month')
        .annotate(avg_price=Avg('predicted_price_per_m2'))
        .order_by('horizon_idx')
    )
    months = []
    for row in monthly_avgs:
        price = _tnd(row['avg_price'])
        months.append({
            'horizon':      row['horizon_idx'],
            'month':        str(row['forecast_month']),
            'month_label':  _month_label(row['forecast_month']),
            'price_per_m2': price,
            'lower':        round(price * (1 - MAPE), 2),
            'upper':        round(price * (1 + MAPE), 2),
        })
    if not months:
        return None

    first = months[0]['price_per_m2']
    mid   = months[5]['price_per_m2'] if len(months) >= 6 else first
    last  = months[-1]['price_per_m2']
    g6    = round((mid  - first) / first * 100, 2) if first else 0
    g12   = round((last - first) / first * 100, 2) if first else 0

    return {
        'governorate':      governorate,
        'property_type':    property_type,
        'delegation_count': qs.values('delegation_name').distinct().count(),
        'months':           months,
        'top_delegations':  _get_top_delegations(governorate, property_type, 5),
        'summary': {
            'current_price_per_m2': first,
            'price_6m':             mid,
            'price_12m':            last,
            'growth_pct_6m':        g6,
            'growth_pct_12m':       g12,
            'trend':                _trend(g12),
        },
    }


def _get_top_delegations(governorate: str, property_type: str, limit: int = 5):
    from forecast.models import DelegationForecast
    from django.db.models import Avg

    gq = _gov_q(governorate)
    d1  = (DelegationForecast.objects
           .filter(gq, property_type=property_type, horizon_idx=1)
           .values('delegation_name').annotate(avg1=Avg('predicted_price_per_m2')))
    d12 = (DelegationForecast.objects
           .filter(gq, property_type=property_type, horizon_idx=12)
           .values('delegation_name').annotate(avg12=Avg('predicted_price_per_m2')))

    d1_map  = {r['delegation_name']: r['avg1']  for r in d1}
    d12_map = {r['delegation_name']: r['avg12'] for r in d12}

    result = []
    for name, price1 in d1_map.items():
        if not price1:
            continue
        price12 = d12_map.get(name, price1)
        growth  = round((price12 - price1) / price1 * 100, 2) if price1 else 0
        result.append({
            'delegation':     name,
            'price_jan_tnd':  _tnd(price1),
            'price_dec_tnd':  _tnd(price12),
            'growth_pct_12m': growth,
        })
    result.sort(key=lambda x: x['growth_pct_12m'], reverse=True)
    return result[:limit]


# ── National top-movers ───────────────────────────────────────────────────────

def get_national_summary(property_type: str = 'apartment'):
    from forecast.models import DelegationForecast
    from django.db.models import Avg

    d1_qs  = (DelegationForecast.objects.filter(horizon_idx=1,  property_type=property_type)
              .values('delegation_name', 'governorate').annotate(avg1=Avg('predicted_price_per_m2')))
    d12_qs = (DelegationForecast.objects.filter(horizon_idx=12, property_type=property_type)
              .values('delegation_name').annotate(avg12=Avg('predicted_price_per_m2')))

    d1_map  = {r['delegation_name']: (r['avg1'], r['governorate']) for r in d1_qs}
    d12_map = {r['delegation_name']: r['avg12'] for r in d12_qs}

    dels = []
    for name, (price1, gov) in d1_map.items():
        if not price1:
            continue
        price12 = d12_map.get(name, price1)
        growth  = round((price12 - price1) / price1 * 100, 2) if price1 else 0
        dels.append({
            'delegation':     name,
            'governorate':    gov,
            'price_jan_tnd':  _tnd(price1),
            'price_dec_tnd':  _tnd(price12),
            'growth_pct_12m': growth,
        })
    dels.sort(key=lambda x: x['growth_pct_12m'], reverse=True)
    return {
        'property_type':     property_type,
        'top_delegations':   dels[:10],
        'total_delegations': len(dels),
    }


# ── Location lists ─────────────────────────────────────────────────────────────

# Canonical governorate names (matches CSV / investor models)
_GOV_CANONICAL = {
    'beja':       'Béja',       'béja':       'Béja',
    'manouba':    'La Manouba', 'la manouba': 'La Manouba',
    'gabes':      'Gabès',      'gabès':      'Gabès',
    'medenine':   'Médenine',   'médenine':   'Médenine',
    'kebili':     'Kébili',     'kébili':     'Kébili',
    'kef':        'Le Kef',     'le kef':     'Le Kef',
}

# All known aliases for each canonical name (for OR-queries)
_GOV_VARIANTS: dict[str, list[str]] = {
    'Béja':       ['Béja', 'Beja'],
    'La Manouba': ['La Manouba', 'Manouba'],
    'Gabès':      ['Gabès', 'Gabes'],
    'Médenine':   ['Médenine', 'Medenine'],
    'Kébili':     ['Kébili', 'Kebili'],
    'Le Kef':     ['Le Kef', 'Kef'],
}


def _canonical_gov(name: str) -> str:
    return _GOV_CANONICAL.get(name.strip().lower(), name.strip())


def list_governorates_with_forecasts():
    from forecast.models import DelegationPriceData
    raw = (
        DelegationPriceData.objects
        .exclude(governorate='')
        .values_list('governorate', flat=True)
        .distinct()
    )
    # Normalize accents/prefixes and deduplicate
    seen: set[str] = set()
    result = []
    for g in raw:
        canonical = _canonical_gov(g)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return sorted(result)


def list_delegations_for_governorate(governorate: str):
    from forecast.models import DelegationPriceData
    from django.db.models import Q

    canonical = _canonical_gov(governorate)
    variants  = _GOV_VARIANTS.get(canonical, [canonical])

    q = Q()
    for v in variants:
        q |= Q(governorate__iexact=v)

    return sorted(
        DelegationPriceData.objects
        .filter(q)
        .values_list('delegation_name', flat=True)
        .distinct()
    )
