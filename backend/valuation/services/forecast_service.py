"""
Forecast service — query layer over DelegationForecast.
All prices stored in millimes (1 TND = 1000 millimes); converts to TND/m2 before returning.
"""
from __future__ import annotations
import logging
from datetime import date

logger = logging.getLogger(__name__)
MAPE = 2.92 / 100


def _tnd(millimes):
    return round(millimes / 1000, 2)


def _month_label(d):
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.strftime("%b %Y")


def _trend(growth_pct):
    if growth_pct >= 2:
        return "rising"
    if growth_pct <= -2:
        return "falling"
    return "stable"


def get_delegation_forecast(delegation_name):
    from valuation.models import DelegationForecast
    qs = (DelegationForecast.objects
          .filter(delegation_name__iexact=delegation_name)
          .order_by("horizon_idx"))
    rows = list(qs)
    if not rows:
        return None
    months = []
    for r in rows:
        price = _tnd(r.predicted_price_per_m2)
        months.append({
            "horizon": r.horizon_idx,
            "month": str(r.forecast_month),
            "month_label": _month_label(r.forecast_month),
            "price_per_m2": price,
            "lower": round(price * (1 - MAPE), 2),
            "upper": round(price * (1 + MAPE), 2),
        })
    first = months[0]["price_per_m2"]
    mid   = months[5]["price_per_m2"] if len(months) >= 6 else first
    last  = months[-1]["price_per_m2"]
    g6  = round((mid  - first) / first * 100, 2) if first else 0
    g12 = round((last - first) / first * 100, 2) if first else 0
    return {
        "delegation": rows[0].delegation_name,
        "governorate": rows[0].governorate,
        "forecast_origin": str(rows[0].forecast_origin),
        "model_mape_pct": rows[0].model_mape_pct,
        "months": months,
        "summary": {
            "current_price_per_m2": first,
            "price_6m": mid,
            "price_12m": last,
            "growth_pct_6m": g6,
            "growth_pct_12m": g12,
            "trend": _trend(g12),
        },
    }


def get_governorate_forecast_summary(governorate):
    from valuation.models import DelegationForecast
    from django.db.models import Avg
    qs = DelegationForecast.objects.filter(governorate__iexact=governorate)
    if not qs.exists():
        return None
    monthly_avgs = (qs.values("horizon_idx", "forecast_month")
                    .annotate(avg_price=Avg("predicted_price_per_m2"))
                    .order_by("horizon_idx"))
    months = []
    for row in monthly_avgs:
        price = _tnd(row["avg_price"])
        months.append({
            "horizon": row["horizon_idx"],
            "month": str(row["forecast_month"]),
            "month_label": _month_label(row["forecast_month"]),
            "price_per_m2": price,
            "lower": round(price * (1 - MAPE), 2),
            "upper": round(price * (1 + MAPE), 2),
        })
    if not months:
        return None
    first = months[0]["price_per_m2"]
    mid   = months[5]["price_per_m2"] if len(months) >= 6 else first
    last  = months[-1]["price_per_m2"]
    g6  = round((mid  - first) / first * 100, 2) if first else 0
    g12 = round((last - first) / first * 100, 2) if first else 0
    return {
        "governorate": governorate,
        "delegation_count": qs.values("delegation_name").distinct().count(),
        "months": months,
        "top_delegations": _get_top_delegations(governorate, 5),
        "summary": {
            "current_price_per_m2": first,
            "price_6m": mid,
            "price_12m": last,
            "growth_pct_6m": g6,
            "growth_pct_12m": g12,
            "trend": _trend(g12),
        },
    }


def get_national_summary():
    from valuation.models import DelegationForecast
    from django.db.models import Avg
    h1_qs  = (DelegationForecast.objects.filter(horizon_idx=1)
              .values("governorate").annotate(avg1=Avg("predicted_price_per_m2")))
    h12_qs = (DelegationForecast.objects.filter(horizon_idx=12)
              .values("governorate").annotate(avg12=Avg("predicted_price_per_m2")))
    h1_map  = {r["governorate"]: r["avg1"]  for r in h1_qs}
    h12_map = {r["governorate"]: r["avg12"] for r in h12_qs}
    govs = []
    for gov, price1 in h1_map.items():
        if not gov or not price1:
            continue
        price12 = h12_map.get(gov, price1)
        growth  = round((price12 - price1) / price1 * 100, 2) if price1 else 0
        govs.append({
            "governorate": gov,
            "price_jan_tnd": _tnd(price1),
            "price_dec_tnd": _tnd(price12),
            "growth_pct_12m": growth,
            "trend": _trend(growth),
        })
    govs.sort(key=lambda x: x["growth_pct_12m"], reverse=True)
    d1_qs  = (DelegationForecast.objects.filter(horizon_idx=1)
              .values("delegation_name", "governorate")
              .annotate(avg1=Avg("predicted_price_per_m2")))
    d12_qs = (DelegationForecast.objects.filter(horizon_idx=12)
              .values("delegation_name").annotate(avg12=Avg("predicted_price_per_m2")))
    d1_map  = {r["delegation_name"]: (r["avg1"], r["governorate"]) for r in d1_qs}
    d12_map = {r["delegation_name"]: r["avg12"] for r in d12_qs}
    dels = []
    for name, (price1, gov) in d1_map.items():
        if not price1:
            continue
        price12 = d12_map.get(name, price1)
        growth  = round((price12 - price1) / price1 * 100, 2) if price1 else 0
        dels.append({
            "delegation": name,
            "governorate": gov,
            "price_jan_tnd": _tnd(price1),
            "price_dec_tnd": _tnd(price12),
            "growth_pct_12m": growth,
        })
    dels.sort(key=lambda x: x["growth_pct_12m"], reverse=True)
    return {
        "top_governorates": govs[:10],
        "top_delegations": dels[:10],
        "total_governorates": len(govs),
        "total_delegations": len(dels),
    }


def _get_top_delegations(governorate, limit=5):
    from valuation.models import DelegationForecast
    from django.db.models import Avg
    d1  = (DelegationForecast.objects
           .filter(governorate__iexact=governorate, horizon_idx=1)
           .values("delegation_name").annotate(avg1=Avg("predicted_price_per_m2")))
    d12 = (DelegationForecast.objects
           .filter(governorate__iexact=governorate, horizon_idx=12)
           .values("delegation_name").annotate(avg12=Avg("predicted_price_per_m2")))
    d1_map  = {r["delegation_name"]: r["avg1"]  for r in d1}
    d12_map = {r["delegation_name"]: r["avg12"] for r in d12}
    result = []
    for name, price1 in d1_map.items():
        if not price1:
            continue
        price12 = d12_map.get(name, price1)
        growth  = round((price12 - price1) / price1 * 100, 2) if price1 else 0
        result.append({
            "delegation": name,
            "price_jan_tnd": _tnd(price1),
            "price_dec_tnd": _tnd(price12),
            "growth_pct_12m": growth,
        })
    result.sort(key=lambda x: x["growth_pct_12m"], reverse=True)
    return result[:limit]


def list_governorates_with_forecasts():
    from valuation.models import DelegationForecast
    return sorted(
        DelegationForecast.objects
        .exclude(governorate="").order_by("governorate").values_list("governorate", flat=True).distinct()
    )


def list_delegations_for_governorate(governorate):
    from valuation.models import DelegationForecast
    return sorted(
        DelegationForecast.objects
        .filter(governorate__iexact=governorate).order_by("delegation_name").values_list("delegation_name", flat=True).distinct()
    )

