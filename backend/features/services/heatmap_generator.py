from __future__ import annotations

from typing import Dict, List, Tuple

from django.db.models import Avg

from core.models import Delegation, Property


def _safe_div(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _min_max_normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 0.0
    return max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))


def get_heat_color(intensity: float) -> str:
    """Map intensity [0,1] to a blue -> yellow -> red palette."""
    if intensity < 0.33:
        return "#2563EB"
    if intensity < 0.66:
        return "#F59E0B"
    return "#DC2626"


def _resolve_point(delegation: Delegation) -> Tuple[float | None, float | None]:
    if delegation.centroid_lat is not None and delegation.centroid_lon is not None:
        return float(delegation.centroid_lat), float(delegation.centroid_lon)

    prop_avg = Property.objects.filter(delegation=delegation, is_active=True).aggregate(
        avg_lat=Avg("latitude"),
        avg_lon=Avg("longitude"),
    )
    if prop_avg["avg_lat"] is not None and prop_avg["avg_lon"] is not None:
        return float(prop_avg["avg_lat"]), float(prop_avg["avg_lon"])

    if delegation.region and delegation.region.latitude is not None and delegation.region.longitude is not None:
        return float(delegation.region.latitude), float(delegation.region.longitude)

    return None, None


def generate_price_heatmap() -> Dict:
    """Return GeoJSON FeatureCollection for delegation-level price heat."""
    delegations = list(Delegation.objects.select_related("region").all())

    values: List[Tuple[Delegation, float]] = []
    for delegation in delegations:
        avg_price = (
            Property.objects.filter(delegation=delegation, is_active=True)
            .aggregate(v=Avg("price"))
            .get("v")
        )
        if avg_price is not None:
            values.append((delegation, float(avg_price)))

    if not values:
        return {"type": "FeatureCollection", "features": []}

    min_value = min(v for _, v in values)
    max_value = max(v for _, v in values)

    features = []
    for delegation, avg_price in values:
        lat, lon = _resolve_point(delegation)
        if lat is None or lon is None:
            continue

        intensity = _min_max_normalize(avg_price, min_value, max_value)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
                "properties": {
                    "delegation_id": delegation.id,
                    "delegation_name": delegation.name,
                    "governorate": delegation.region.governorate,
                    "avg_price_tnd": round(avg_price, 2),
                    "intensity": round(intensity, 4),
                    "color": get_heat_color(intensity),
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def generate_demand_heatmap() -> Dict:
    """Return GeoJSON FeatureCollection for delegation-level supply pressure heat."""
    delegations = list(Delegation.objects.select_related("region").all())

    pressures: List[Tuple[Delegation, float, int]] = []
    for delegation in delegations:
        listing_count = Property.objects.filter(delegation=delegation, is_active=True).count()
        population = delegation.population or 0
        pressure = (_safe_div(listing_count, population) * 1000.0) if population > 0 else 0.0
        pressures.append((delegation, pressure, listing_count))

    if not pressures:
        return {"type": "FeatureCollection", "features": []}

    min_value = min(v for _, v, _ in pressures)
    max_value = max(v for _, v, _ in pressures)

    features = []
    for delegation, pressure, listing_count in pressures:
        lat, lon = _resolve_point(delegation)
        if lat is None or lon is None:
            continue

        intensity = _min_max_normalize(pressure, min_value, max_value)
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
                "properties": {
                    "delegation_id": delegation.id,
                    "delegation_name": delegation.name,
                    "governorate": delegation.region.governorate,
                    "supply_pressure": round(pressure, 4),
                    "listing_count": int(listing_count),
                    "intensity": round(intensity, 4),
                    "color": get_heat_color(intensity),
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}
