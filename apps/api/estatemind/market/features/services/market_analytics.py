from __future__ import annotations

import json
import math
from datetime import timedelta
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Tuple

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy is expected, but keep a fallback
    np = None

from django.db.models import Avg, Count, Q

from estatemind.market.core.models import ClimateRisk, Delegation, DelegationMarketSnapshot, Property


from config.paths import ARTIFACTS_DIR

_ARTIFACT_PATH = ARTIFACTS_DIR / "features" / "market_intelligence_calibration.json"
_DEFAULT_WEIGHTS = {
    "price_trend": 0.42,
    "listing_volume": 0.28,
    "climate_risk": 0.18,
    "spatial_lag": 0.12,
}
_DEFAULT_CALIBRATION = {
    "version": 1,
    "updated_at": None,
    "window_months": 6,
    "sample_size": 0,
    "directional_accuracy": 0.0,
    "top_decile_hit_rate": 0.0,
    "correlation_with_realized_return": 0.0,
    "weights": _DEFAULT_WEIGHTS,
}


def _normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def _is_rent_listing(property_obj: Property) -> bool:
    # For current schema, transaction type is embedded by the import command in description.
    desc = _normalize_text(property_obj.description)
    return "type: rent" in desc


def _is_sale_listing(property_obj: Property) -> bool:
    desc = _normalize_text(property_obj.description)
    return "type: sale" in desc


def _safe_div(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def _load_calibration_profile() -> Dict[str, Any]:
    if not _ARTIFACT_PATH.exists():
        return dict(_DEFAULT_CALIBRATION)

    try:
        with _ARTIFACT_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        weights = dict(_DEFAULT_WEIGHTS)
        weights.update(payload.get("weights", {}))
        payload["weights"] = weights
        for key, value in _DEFAULT_CALIBRATION.items():
            payload.setdefault(key, value)
        return payload
    except Exception:
        return dict(_DEFAULT_CALIBRATION)


def _save_calibration_profile(payload: Dict[str, Any]) -> None:
    _ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _ARTIFACT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def _normalize_component(value: float, scale: float) -> float:
    if not scale:
        return 0.0
    return _clamp(float(value) / float(scale), -1.0, 1.0)


def _climate_penalty(region: str | None) -> float:
    if not region:
        return 0.35
    risk = ClimateRisk.objects.select_related("region").filter(region__governorate__iexact=region).first()
    if risk is None:
        return 0.35
    return _clamp((float(risk.combined_risk_score or 0.0) / 100.0), 0.0, 1.0)


def _snapshot_score_components(snapshot: DelegationMarketSnapshot) -> Dict[str, float]:
    supply_pressure = float(snapshot.supply_pressure or 0.0)
    listing_count = float(snapshot.listing_count or 0.0)
    median_price = float(snapshot.median_price_per_sqm or 0.0)
    median_days = float(snapshot.median_days_on_market or 0.0)
    trend_6m = 0.0
    volume_change = 0.0

    previous_snapshot = (
        DelegationMarketSnapshot.objects.filter(
            delegation=snapshot.delegation,
            as_of_date__lt=snapshot.as_of_date,
        )
        .order_by("-as_of_date")
        .first()
    )
    if previous_snapshot and previous_snapshot.median_price_per_sqm:
        trend_6m = (
            (float(snapshot.median_price_per_sqm or 0.0) - float(previous_snapshot.median_price_per_sqm))
            / float(previous_snapshot.median_price_per_sqm)
        ) * 100.0
        volume_change = (
            (float(snapshot.listing_count or 0.0) - float(previous_snapshot.listing_count or 0.0))
            / max(float(previous_snapshot.listing_count or 1.0), 1.0)
        ) * 100.0

    return {
        "price_trend_6m_pct": trend_6m,
        "listing_volume_change_pct": volume_change,
        "supply_pressure": supply_pressure,
        "listing_count": listing_count,
        "median_price_per_sqm": median_price,
        "median_days_on_market": median_days,
        "history_depth_months": max(
            0.0,
            (snapshot.as_of_date - (previous_snapshot.as_of_date if previous_snapshot else snapshot.as_of_date)).days / 30.4,
        ),
    }


def _compute_spatial_lag(delegation: Delegation, peer_signals: Dict[int, Dict[str, Any]]) -> Tuple[float, int, List[Dict[str, Any]]]:
    if delegation.centroid_lat is None or delegation.centroid_lon is None:
        if delegation.region and delegation.region.latitude is not None and delegation.region.longitude is not None:
            base_lat = float(delegation.region.latitude)
            base_lon = float(delegation.region.longitude)
        else:
            return 0.0, 0, []
    else:
        base_lat = float(delegation.centroid_lat)
        base_lon = float(delegation.centroid_lon)

    weighted_sum = 0.0
    weight_total = 0.0
    neighbors: List[Dict[str, Any]] = []

    for other_id, other in peer_signals.items():
        if other_id == delegation.id:
            continue
        other_delegation = other.get("delegation")
        if other_delegation is None:
            continue

        if other_delegation.centroid_lat is None or other_delegation.centroid_lon is None:
            if not (other_delegation.region and other_delegation.region.latitude is not None and other_delegation.region.longitude is not None):
                continue
            other_lat = float(other_delegation.region.latitude)
            other_lon = float(other_delegation.region.longitude)
        else:
            other_lat = float(other_delegation.centroid_lat)
            other_lon = float(other_delegation.centroid_lon)

        distance_km = _haversine_km(base_lat, base_lon, other_lat, other_lon)
        if distance_km > 120.0:
            continue

        weight = math.exp(-distance_km / 40.0)
        base_score = float(other.get("base_score", 50.0))
        weighted_sum += base_score * weight
        weight_total += weight
        neighbors.append({
            "delegation_id": other_id,
            "delegation_name": other_delegation.name,
            "distance_km": round(distance_km, 2),
            "influence_weight": round(weight, 4),
            "neighbor_score": round(base_score, 2),
        })

    if not weight_total:
        return 0.0, 0, []

    spatial_score = weighted_sum / weight_total
    spatial_lag = _clamp((spatial_score - 50.0) / 50.0, -1.0, 1.0)
    neighbors.sort(key=lambda item: item["influence_weight"], reverse=True)
    return spatial_lag, len(neighbors), neighbors[:5]


def _score_from_signals(signals: Dict[str, Any], weights: Dict[str, float]) -> Tuple[float, List[Dict[str, Any]]]:
    price_trend_norm = _normalize_component(signals.get("price_trend_6m_pct", 0.0), 20.0)
    listing_volume_norm = _normalize_component(signals.get("listing_volume_change_pct", 0.0), 30.0)
    supply_pressure_norm = _normalize_component(signals.get("supply_pressure", 0.0) - 2.0, 6.0)
    climate_penalty_norm = _clamp(float(signals.get("climate_penalty", 0.35)), 0.0, 1.0)
    spatial_lag_norm = _clamp(float(signals.get("spatial_lag", 0.0)), -1.0, 1.0)

    price_trend_weight = float(weights.get("price_trend", _DEFAULT_WEIGHTS["price_trend"]))
    listing_volume_weight = float(weights.get("listing_volume", _DEFAULT_WEIGHTS["listing_volume"]))
    climate_risk_weight = float(weights.get("climate_risk", _DEFAULT_WEIGHTS["climate_risk"]))
    spatial_lag_weight = float(weights.get("spatial_lag", _DEFAULT_WEIGHTS["spatial_lag"]))

    price_trend_impact = 22.0 * price_trend_weight * price_trend_norm
    listing_volume_impact = 14.0 * listing_volume_weight * listing_volume_norm
    supply_pressure_impact = 8.0 * listing_volume_weight * supply_pressure_norm
    climate_impact = -18.0 * climate_risk_weight * climate_penalty_norm
    spatial_impact = 12.0 * spatial_lag_weight * spatial_lag_norm

    score = 50.0 + price_trend_impact + listing_volume_impact + supply_pressure_impact + climate_impact + spatial_impact
    score = _clamp(score, 0.0, 100.0)

    drivers = [
        {
            "driver": "Price trend",
            "direction": "positive" if price_trend_impact >= 0 else "negative",
            "raw_value": round(float(signals.get("price_trend_6m_pct", 0.0)), 2),
            "weight": round(price_trend_weight, 3),
            "impact": round(price_trend_impact, 2),
        },
        {
            "driver": "Listing activity",
            "direction": "positive" if (listing_volume_impact + supply_pressure_impact) >= 0 else "negative",
            "raw_value": round(float(signals.get("listing_volume_change_pct", 0.0)), 2),
            "weight": round(listing_volume_weight, 3),
            "impact": round(listing_volume_impact + supply_pressure_impact, 2),
        },
        {
            "driver": "Climate risk",
            "direction": "negative" if climate_impact < 0 else "positive",
            "raw_value": round(climate_penalty_norm * 100.0, 2),
            "weight": round(climate_risk_weight, 3),
            "impact": round(climate_impact, 2),
        },
        {
            "driver": "Spatial momentum",
            "direction": "positive" if spatial_impact >= 0 else "negative",
            "raw_value": round(spatial_lag_norm * 100.0, 2),
            "weight": round(spatial_lag_weight, 3),
            "impact": round(spatial_impact, 2),
        },
    ]
    drivers.sort(key=lambda item: abs(item["impact"]), reverse=True)
    return score, drivers[:3]


def _confidence_from_signals(signals: Dict[str, Any], neighbor_count: int) -> Tuple[str, float, float]:
    listing_count = float(signals.get("listing_count", 0.0) or 0.0)
    history_depth_months = float(signals.get("history_depth_months", 0.0) or 0.0)
    climate_penalty = float(signals.get("climate_penalty", 0.35) or 0.35)
    volatility = abs(float(signals.get("price_trend_6m_pct", 0.0))) + abs(float(signals.get("listing_volume_change_pct", 0.0)))

    confidence_score = (
        min(listing_count / 400.0, 1.0) * 0.4
        + min(history_depth_months / 12.0, 1.0) * 0.35
        + min(neighbor_count / 6.0, 1.0) * 0.25
    )
    if confidence_score >= 0.75:
        level = "HIGH"
    elif confidence_score >= 0.45:
        level = "MEDIUM"
    else:
        level = "LOW"

    uncertainty_band_pct = _clamp(18.0 - confidence_score * 10.0 + min(volatility, 40.0) * 0.15 + climate_penalty * 4.0, 4.0, 24.0)
    return level, round(confidence_score, 3), round(uncertainty_band_pct, 2)


def _build_market_intelligence_bundle() -> Tuple[Dict[int, Dict[str, Any]], Dict[str, Any]]:
    delegations = list(Delegation.objects.select_related("region").all())
    calibration = _load_calibration_profile()

    peer_signals: Dict[int, Dict[str, Any]] = {}
    for delegation in delegations:
        properties = list(
            Property.objects.filter(delegation=delegation, is_active=True).only(
                "id", "price", "area_sqm", "property_type", "description"
            )
        )
        listing_count = len(properties)
        sale_properties = [p for p in properties if _is_sale_listing(p)]
        rental_properties = [p for p in properties if _is_rent_listing(p)]
        if not sale_properties and not rental_properties:
            sale_properties = properties

        price_per_m2_values = [p.price / p.area_sqm for p in properties if p.area_sqm and p.area_sqm > 0]
        median_price_per_m2 = float(median(price_per_m2_values)) if price_per_m2_values else 0.0
        avg_price_tnd = _safe_div(sum(p.price for p in sale_properties), len(sale_properties))
        avg_monthly_rental = _safe_div(sum(p.price for p in rental_properties), len(rental_properties))

        snapshot = (
            DelegationMarketSnapshot.objects.filter(delegation=delegation)
            .order_by("-as_of_date")
            .first()
        )
        if snapshot is not None:
            snapshot_signals = _snapshot_score_components(snapshot)
            supply_pressure = snapshot_signals["supply_pressure"]
            price_trend_6m_pct = snapshot_signals["price_trend_6m_pct"]
            listing_volume_change_pct = snapshot_signals["listing_volume_change_pct"]
            history_depth_months = snapshot_signals["history_depth_months"]
            median_days_on_market = snapshot_signals["median_days_on_market"]
        else:
            supply_pressure = (_safe_div(listing_count, delegation.population or 0) * 1000.0) if delegation.population else 0.0
            price_trend_6m_pct = 0.0
            listing_volume_change_pct = 0.0
            history_depth_months = 0.0
            median_days_on_market = 45.0

        peer_signals[delegation.id] = {
            "delegation": delegation,
            "delegation_id": delegation.id,
            "delegation_name": delegation.name,
            "governorate": delegation.region.governorate,
            "listing_count": listing_count,
            "sale_count": len(sale_properties),
            "rental_count": len(rental_properties),
            "avg_price_tnd": round(avg_price_tnd, 2),
            "median_price_per_m2": round(median_price_per_m2, 2),
            "avg_monthly_rental": round(avg_monthly_rental, 2),
            "supply_pressure": round(supply_pressure, 4),
            "rent_ratio": _safe_div(len(rental_properties), listing_count),
            "property_type_distribution": {
                ptype: round((_safe_div(count, listing_count) * 100.0), 1)
                for ptype, count in sorted(
                    {p.property_type: sum(1 for x in properties if x.property_type == p.property_type) for p in properties}.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            },
            "price_trend_6m_pct": round(price_trend_6m_pct, 2),
            "listing_volume_change_pct": round(listing_volume_change_pct, 2),
            "climate_penalty": _climate_penalty(delegation.region.governorate),
            "history_depth_months": round(history_depth_months, 2),
            "median_days_on_market": round(median_days_on_market, 2),
            "snapshot_date": snapshot.as_of_date.isoformat() if snapshot else None,
        }

    for delegation in delegations:
        spatial_lag, neighbor_count, neighbors = _compute_spatial_lag(delegation, peer_signals)
        peer_signals[delegation.id]["spatial_lag"] = round(spatial_lag, 4)
        peer_signals[delegation.id]["neighbor_count"] = neighbor_count
        peer_signals[delegation.id]["top_neighbors"] = neighbors

        score, drivers = _score_from_signals(peer_signals[delegation.id], calibration.get("weights", _DEFAULT_WEIGHTS))
        level, confidence_score, uncertainty_band_pct = _confidence_from_signals(peer_signals[delegation.id], neighbor_count)

        peer_signals[delegation.id]["base_score"] = score
        peer_signals[delegation.id]["opportunity_score"] = round(score, 2)
        peer_signals[delegation.id]["confidence_level"] = level
        peer_signals[delegation.id]["confidence_score"] = confidence_score
        peer_signals[delegation.id]["uncertainty_band_pct"] = uncertainty_band_pct
        peer_signals[delegation.id]["score_range"] = {
            "min": round(_clamp(score - uncertainty_band_pct, 0.0, 100.0), 2),
            "max": round(_clamp(score + uncertainty_band_pct, 0.0, 100.0), 2),
        }
        peer_signals[delegation.id]["top_drivers"] = drivers
        peer_signals[delegation.id]["calibration"] = calibration

    public_bundle: Dict[int, Dict[str, Any]] = {}
    for delegation_id, payload in peer_signals.items():
        public_bundle[delegation_id] = {
            key: value
            for key, value in payload.items()
            if key not in {"delegation", "base_score"}
        }

    return public_bundle, calibration


class DelegationAnalytics:
    """Compute market analytics for one or all delegations."""

    @staticmethod
    def get_delegation_kpis(delegation_id: int) -> Dict:
        delegation = Delegation.objects.select_related("region").filter(id=delegation_id).first()
        if delegation is None:
            return {
                "delegation_id": delegation_id,
                "delegation_name": "Unknown",
                "governorate": "Unknown",
                "listing_count": 0,
                "sale_count": 0,
                "rental_count": 0,
                "avg_price_tnd": 0.0,
                "median_price_per_m2": 0.0,
                "avg_monthly_rental": 0.0,
                "supply_pressure": 0.0,
                "rent_ratio": 0.0,
                "property_type_distribution": {},
                "price_trend_6m_pct": 0.0,
                "listing_volume_change_pct": 0.0,
                "climate_penalty": 0.35,
                "spatial_lag": 0.0,
                "neighbor_count": 0,
                "confidence_level": "LOW",
                "confidence_score": 0.0,
                "uncertainty_band_pct": 0.0,
                "score_range": {"min": 0.0, "max": 0.0},
                "top_drivers": [],
                "opportunity_score": 0.0,
            }
        bundle, _ = _build_market_intelligence_bundle()
        return bundle.get(delegation_id, {
            "delegation_id": delegation.id,
            "delegation_name": delegation.name,
            "governorate": delegation.region.governorate,
            "listing_count": 0,
            "sale_count": 0,
            "rental_count": 0,
            "avg_price_tnd": 0.0,
            "median_price_per_m2": 0.0,
            "avg_monthly_rental": 0.0,
            "supply_pressure": 0.0,
            "rent_ratio": 0.0,
            "property_type_distribution": {},
            "price_trend_6m_pct": 0.0,
            "listing_volume_change_pct": 0.0,
            "climate_penalty": 0.35,
            "spatial_lag": 0.0,
            "neighbor_count": 0,
            "confidence_level": "LOW",
            "confidence_score": 0.0,
            "uncertainty_band_pct": 0.0,
            "score_range": {"min": 0.0, "max": 0.0},
            "top_drivers": [],
            "opportunity_score": 0.0,
        })

    @staticmethod
    def get_all_delegations_summary() -> Dict:
        delegations = list(Delegation.objects.select_related("region").all())
        all_active_properties = Property.objects.filter(is_active=True)
        # Calculate national median price per m² (not total price)
        sale_properties = [
            p
            for p in all_active_properties.only("price", "area_sqm", "description")
            if _is_sale_listing(p) or "type:" not in _normalize_text(p.description)
        ]
        sale_prices_per_sqm = [
            float(p.price) / float(p.area_sqm)
            for p in sale_properties
            if p.area_sqm and p.area_sqm > 0
        ]
        # Use median to avoid outlier distortion
        avg_price_per_sqm = median(sale_prices_per_sqm) if sale_prices_per_sqm else 0.0

        bundle, calibration = _build_market_intelligence_bundle()
        kpis: List[Dict] = [bundle[d.id] for d in delegations if d.id in bundle]

        return {
            "total_delegations": len(delegations),
            "total_listings": all_active_properties.count(),
            "avg_price_national": round(avg_price_per_sqm, 2),
            "delegations_kpis": kpis,
            "calibration": calibration,
        }


def calculate_opportunity_score(kpis: Dict) -> float:
    """Composite score in [0, 100] with calibrated weights and spatial context."""
    weights = _load_calibration_profile().get("weights", _DEFAULT_WEIGHTS)
    signals = {
        "price_trend_6m_pct": float(kpis.get("price_trend_6m_pct", 0.0) or 0.0),
        "listing_volume_change_pct": float(kpis.get("listing_volume_change_pct", 0.0) or 0.0),
        "supply_pressure": float(kpis.get("supply_pressure", 0.0) or 0.0),
        "climate_penalty": float(kpis.get("climate_penalty", 0.35) or 0.35),
        "spatial_lag": float(kpis.get("spatial_lag", 0.0) or 0.0),
    }
    score, _ = _score_from_signals(signals, weights)
    return score


def run_market_intelligence_calibration(window_months: int = 6, persist: bool = True) -> Dict[str, Any]:
    """Recalibrate heuristic weights against realized six-month outcomes."""
    snapshots = list(
        DelegationMarketSnapshot.objects.select_related("delegation__region").order_by("delegation_id", "as_of_date")
    )
    if len(snapshots) < 2:
        report = dict(_DEFAULT_CALIBRATION)
        report["status"] = "insufficient_history"
        report["sample_size"] = len(snapshots)
        return report

    horizon = timedelta(days=int(window_months * 30.4))
    rows: List[Dict[str, float]] = []
    future_returns: List[float] = []
    predictions: List[float] = []

    grouped: Dict[int, List[DelegationMarketSnapshot]] = {}
    for snapshot in snapshots:
        grouped.setdefault(snapshot.delegation_id, []).append(snapshot)

    for delegation_id, delegation_snapshots in grouped.items():
        for index, snapshot in enumerate(delegation_snapshots):
            target_date = snapshot.as_of_date + horizon
            future_snapshot = next(
                (
                    candidate
                    for candidate in delegation_snapshots[index + 1 :]
                    if candidate.as_of_date >= target_date
                ),
                None,
            )
            if future_snapshot is None or not snapshot.median_price_per_sqm or not future_snapshot.median_price_per_sqm:
                continue

            realized_return = (
                (float(future_snapshot.median_price_per_sqm) - float(snapshot.median_price_per_sqm))
                / float(snapshot.median_price_per_sqm)
            ) * 100.0
            trend_feature = _normalize_component(float(snapshot.forecast_6m or 0.0), 20.0)
            volume_feature = _normalize_component(float(snapshot.listing_count or 0.0), 400.0)
            climate_feature = _clamp(
                (
                    0.2 if snapshot.climate_risk_level == "low" else
                    0.45 if snapshot.climate_risk_level == "medium" else
                    0.7 if snapshot.climate_risk_level == "high" else
                    0.9
                ),
                0.0,
                1.0,
            )
            rows.append({
                "price_trend": trend_feature,
                "listing_volume": volume_feature,
                "climate_risk": climate_feature,
                "spatial_lag": 0.0,
            })
            future_returns.append(realized_return)

            pseudo_score = 50.0 + 22.0 * trend_feature + 14.0 * volume_feature - 18.0 * climate_feature
            predictions.append(pseudo_score)

    if not rows:
        report = dict(_DEFAULT_CALIBRATION)
        report["status"] = "insufficient_history"
        report["sample_size"] = 0
        return report

    if np is not None and len(rows) >= 4:
        matrix = np.array([[row["price_trend"], row["listing_volume"], row["climate_risk"], row["spatial_lag"]] for row in rows], dtype=float)
        matrix = (matrix - matrix.mean(axis=0)) / (matrix.std(axis=0) + 1e-6)
        target = np.array(future_returns, dtype=float)
        coeffs, *_ = np.linalg.lstsq(matrix, target, rcond=None)
        coeffs = np.abs(coeffs)
        if float(coeffs.sum()) > 0.0:
            weights = {
                "price_trend": float(coeffs[0] / coeffs.sum()),
                "listing_volume": float(coeffs[1] / coeffs.sum()),
                "climate_risk": float(coeffs[2] / coeffs.sum()),
                "spatial_lag": max(_DEFAULT_WEIGHTS["spatial_lag"], float(coeffs[3] / coeffs.sum()) if len(coeffs) > 3 else _DEFAULT_WEIGHTS["spatial_lag"]),
            }
            weight_sum = sum(weights.values()) or 1.0
            weights = {key: round(value / weight_sum, 4) for key, value in weights.items()}
        else:
            weights = dict(_DEFAULT_WEIGHTS)
    else:
        weights = dict(_DEFAULT_WEIGHTS)

    realized_array = future_returns
    prediction_array = predictions
    ordered = sorted(zip(prediction_array, realized_array), key=lambda item: item[0], reverse=True)
    threshold_index = max(1, len(ordered) // 10)
    top_slice = ordered[:threshold_index]
    rest_slice = ordered[threshold_index:]
    top_decile_return = sum(item[1] for item in top_slice) / len(top_slice) if top_slice else 0.0
    rest_return = sum(item[1] for item in rest_slice) / len(rest_slice) if rest_slice else 0.0
    directional_accuracy = sum(
        1 for prediction, realized in zip(prediction_array, realized_array)
        if (prediction >= 50.0 and realized >= 0.0) or (prediction < 50.0 and realized < 0.0)
    ) / len(realized_array)

    correlation = 0.0
    if np is not None and len(realized_array) > 1:
        correlation_matrix = np.corrcoef(np.array(prediction_array, dtype=float), np.array(realized_array, dtype=float))
        if correlation_matrix.shape == (2, 2):
            correlation = float(correlation_matrix[0, 1])

    report = {
        "version": 2,
        "updated_at": None,
        "window_months": window_months,
        "sample_size": len(realized_array),
        "directional_accuracy": round(directional_accuracy, 3),
        "top_decile_hit_rate": round(_safe_div(top_decile_return - rest_return, abs(rest_return) + 1e-6), 3),
        "correlation_with_realized_return": round(correlation, 3),
        "weights": weights,
        "status": "recalibrated" if len(realized_array) >= 4 else "fallback",
    }

    if persist:
        _save_calibration_profile(report)

    return report
