from __future__ import annotations

from statistics import median
from typing import Dict, List

from django.db.models import Avg, Count, Q

from core.models import Delegation, Property


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
                "opportunity_score": 0.0,
            }

        properties = list(
            Property.objects.filter(delegation=delegation, is_active=True).only(
                "id",
                "price",
                "area_sqm",
                "property_type",
                "description",
            )
        )

        if not properties:
            return {
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
                "opportunity_score": 0.0,
            }

        listing_count = len(properties)
        sale_properties = [p for p in properties if _is_sale_listing(p)]
        rental_properties = [p for p in properties if _is_rent_listing(p)]

        # Fallback: if no explicit type labels, treat all as sales to avoid all-zero analytics.
        if not sale_properties and not rental_properties:
            sale_properties = properties

        price_per_m2_values = [
            p.price / p.area_sqm for p in properties if p.area_sqm and p.area_sqm > 0
        ]
        median_price_per_m2 = float(median(price_per_m2_values)) if price_per_m2_values else 0.0

        avg_price_tnd = _safe_div(sum(p.price for p in sale_properties), len(sale_properties))
        avg_monthly_rental = _safe_div(sum(p.price for p in rental_properties), len(rental_properties))

        type_counts: Dict[str, int] = {}
        for p in properties:
            type_counts[p.property_type] = type_counts.get(p.property_type, 0) + 1

        property_type_distribution = {
            ptype: round((_safe_div(count, listing_count) * 100.0), 1)
            for ptype, count in sorted(type_counts.items(), key=lambda item: item[1], reverse=True)
        }

        population = delegation.population or 0
        supply_pressure = (_safe_div(listing_count, population) * 1000.0) if population > 0 else 0.0
        rent_ratio = _safe_div(len(rental_properties), listing_count)

        kpis = {
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
            "rent_ratio": round(rent_ratio, 4),
            "property_type_distribution": property_type_distribution,
        }
        kpis["opportunity_score"] = round(calculate_opportunity_score(kpis), 2)
        return kpis

    @staticmethod
    def get_all_delegations_summary() -> Dict:
        delegations = list(Delegation.objects.select_related("region").all())
        all_active_properties = Property.objects.filter(is_active=True)
        all_sale_prices = [
            p.price
            for p in all_active_properties.only("price", "description")
            if _is_sale_listing(p) or "type:" not in _normalize_text(p.description)
        ]

        kpis: List[Dict] = [
            DelegationAnalytics.get_delegation_kpis(d.id) for d in delegations
        ]

        return {
            "total_delegations": len(delegations),
            "total_listings": all_active_properties.count(),
            "avg_price_national": round(_safe_div(sum(all_sale_prices), len(all_sale_prices)), 2)
            if all_sale_prices
            else 0.0,
            "delegations_kpis": kpis,
        }


def calculate_opportunity_score(kpis: Dict) -> float:
    """
    Composite score in [0, 100].
    Higher score means better investment opportunity under this heuristic.
    """
    score = 50.0

    supply_pressure = float(kpis.get("supply_pressure", 0.0) or 0.0)
    avg_price_tnd = float(kpis.get("avg_price_tnd", 0.0) or 0.0)
    avg_monthly_rental = float(kpis.get("avg_monthly_rental", 0.0) or 0.0)

    if supply_pressure > 5.0:
        score += 15.0
    elif supply_pressure > 2.0:
        score += 8.0

    if avg_price_tnd > 0:
        if avg_price_tnd < 300000:
            score += 20.0
        elif avg_price_tnd < 500000:
            score += 10.0

    if avg_monthly_rental > 0 and avg_price_tnd > 0:
        rental_yield = (avg_monthly_rental * 12.0) / avg_price_tnd
        if rental_yield > 0.08:
            score += 15.0
        elif rental_yield > 0.06:
            score += 8.0

    return max(0.0, min(100.0, score))
