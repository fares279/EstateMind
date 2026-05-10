from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import median
from typing import Iterable

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.models import (
    ClimateRisk,
    Delegation,
    DelegationMarketSegment,
    DelegationMarketSnapshot,
    PriceTrend,
    Property,
    Region,
)


PROPERTY_TYPE_MAP = {
    "apartment": "apartment",
    "house": "house",
    "villa": "villa",
    "land": "land",
    "commercial space": "commercial",
    "commercial": "commercial",
    "office": "office",
    "farm": "farm",
}

TRANSACTION_TYPE_MAP = {
    "sale": "sale",
    "rent": "rent",
}

GOVERNORATE_ALIASES = {
    "beja": "Béja",
    "ben arous": "Ben Arous",
    "bizerte": "Bizerte",
    "gabes": "Gabès",
    "gafsa": "Gafsa",
    "jendouba": "Jendouba",
    "kairouan": "Kairouan",
    "kasserine": "Kasserine",
    "kebili": "Kébili",
    "kef": "Le Kef",
    "mahdia": "Mahdia",
    "manouba": "La Manouba",
    "medenine": "Médenine",
    "monastir": "Monastir",
    "nabeul": "Nabeul",
    "sfax": "Sfax",
    "sidi bouzid": "Sidi Bouzid",
    "siliana": "Siliana",
    "sousse": "Sousse",
    "tataouine": "Tataouine",
    "tozeur": "Tozeur",
    "tunis": "Tunis",
    "zaghouan": "Zaghouan",
    "ariana": "Ariana",
}


@dataclass
class ImportStats:
    regions_created: int = 0
    delegations_created: int = 0
    properties_created: int = 0
    properties_updated: int = 0
    delegation_duplicates_merged: int = 0
    snapshots_built: int = 0
    segments_built: int = 0


def _fix_mojibake(value: str) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    suspicious_tokens = ("Ã", "Â", "â€™", "â€“", "â€”")
    if any(token in cleaned for token in suspicious_tokens):
        try:
            repaired = cleaned.encode("latin1").decode("utf-8")
            if repaired:
                cleaned = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return cleaned.replace("\xa0", " ").strip()


def normalize_label(value: str) -> str:
    return " ".join(_fix_mojibake(value).split())


def normalize_governorate(value: str) -> str:
    cleaned = normalize_label(value)
    key = cleaned.casefold()
    return GOVERNORATE_ALIASES.get(key, cleaned)


def normalize_property_type(value: str) -> str:
    cleaned = normalize_label(value).casefold()
    return PROPERTY_TYPE_MAP.get(cleaned, "commercial")


def normalize_transaction_type(value: str) -> str:
    cleaned = normalize_label(value).casefold()
    return TRANSACTION_TYPE_MAP.get(cleaned, "sale")


def parse_int(value: str | None) -> int:
    if value in (None, ""):
        return 0
    cleaned = normalize_label(str(value)).replace(" ", "").replace(",", "")
    return int(float(cleaned))


def parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    cleaned = normalize_label(str(value)).replace(" ", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_dt(value: str | None):
    if value in (None, ""):
        return None
    parsed = parse_datetime(normalize_label(value))
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.utc)
    return parsed


def _safe_median(values: Iterable[float]) -> float | None:
    values = [float(v) for v in values if v is not None]
    if not values:
        return None
    return float(median(values))


def _safe_average(values: Iterable[float]) -> float | None:
    values = [float(v) for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _distribution(values: list[float]) -> dict:
    values = sorted(v for v in values if v is not None)
    if not values:
        return {}
    return {
        "min": round(values[0], 2),
        "p25": round(values[max(0, int((len(values) - 1) * 0.25))], 2),
        "p50": round(values[max(0, int((len(values) - 1) * 0.50))], 2),
        "p75": round(values[max(0, int((len(values) - 1) * 0.75))], 2),
        "max": round(values[-1], 2),
    }


def _days_on_market(property_obj: Property) -> float | None:
    if not property_obj.posted_at:
        return None
    end = property_obj.scraped_at or timezone.now()
    return max((end - property_obj.posted_at).days, 0)


def _trend_for_region(region: Region, property_type: str | None = None) -> PriceTrend | None:
    queryset = PriceTrend.objects.filter(region=region)
    if property_type and property_type != "all":
        queryset = queryset.filter(property_type=property_type)
    return queryset.order_by("-date").first()


def _climate_for_region(region: Region) -> ClimateRisk | None:
    return ClimateRisk.objects.filter(region=region).first()


@transaction.atomic
def import_market_csvs(delegations_csv: Path, properties_csv: Path, rebuild_aggregates: bool = True) -> ImportStats:
    stats = ImportStats()
    delegation_rows: dict[tuple[str, str], dict] = {}

    with Path(delegations_csv).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            governorate = normalize_governorate(row.get("Governorate", ""))
            delegation_name = normalize_label(row.get("Delegation", ""))
            population_key = "Population (2024)" if "Population (2024)" in row else "Population"
            population = parse_int(row.get(population_key))
            key = (governorate, delegation_name)
            existing = delegation_rows.get(key)
            if existing:
                stats.delegation_duplicates_merged += 1
                if population > existing["population"]:
                    existing["population"] = population
            else:
                delegation_rows[key] = {
                    "governorate": governorate,
                    "delegation": delegation_name,
                    "population": population,
                }

    for payload in delegation_rows.values():
        region, region_created = Region.objects.get_or_create(
            governorate=payload["governorate"],
            defaults={"population": 0},
        )
        if region_created:
            stats.regions_created += 1

        delegation, delegation_created = Delegation.objects.update_or_create(
            region=region,
            name=payload["delegation"],
            defaults={"population": payload["population"]},
        )
        if delegation_created:
            stats.delegations_created += 1

    population_by_region = (
        Delegation.objects.values("region_id")
        .annotate(total_population=Sum("population"))
    )
    for row in population_by_region:
        Region.objects.filter(id=row["region_id"]).update(population=row["total_population"] or 0)

    with Path(properties_csv).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            governorate = normalize_governorate(row.get("governorate", ""))
            delegation_name = normalize_label(row.get("delegation", ""))
            region, region_created = Region.objects.get_or_create(
                governorate=governorate,
                defaults={"population": 0},
            )
            if region_created:
                stats.regions_created += 1

            delegation, delegation_created = Delegation.objects.get_or_create(
                region=region,
                name=delegation_name,
                defaults={"population": 0},
            )
            if delegation_created:
                stats.delegations_created += 1

            price = parse_float(row.get("price_tnd")) or 0.0
            surface = parse_float(row.get("surface_m2")) or 0.0
            price_per_sqm = parse_float(row.get("price_per_m2"))
            if price_per_sqm is None and price > 0 and surface > 0:
                price_per_sqm = price / surface

            defaults = {
                "title": normalize_label(row.get("title", "")),
                "description": (
                    f"{normalize_label(row.get('title', ''))} | "
                    f"Type: {normalize_transaction_type(row.get('transaction_type'))} | "
                    f"Location: {normalize_label(row.get('location_raw', ''))} | "
                    f"Source: {normalize_label(row.get('source', ''))}"
                ),
                "property_type": normalize_property_type(row.get("property_type")),
                "transaction_type": normalize_transaction_type(row.get("transaction_type")),
                "region": region,
                "delegation": delegation,
                "price": price,
                "area_sqm": surface,
                "price_per_sqm": price_per_sqm,
                "rooms": parse_int(row.get("rooms")) or None,
                "bedrooms": parse_int(row.get("bedrooms")) or None,
                "bathrooms": parse_int(row.get("bathrooms")) or None,
                "latitude": None,
                "longitude": None,
                "location_raw": normalize_label(row.get("location_raw", "")),
                "source": normalize_label(row.get("source", "")),
                "currency": normalize_label(row.get("currency", "")) or "TND",
                "posted_at": parse_dt(row.get("posted_at")),
                "scraped_at": parse_dt(row.get("scraped_at")),
                "is_active": True,
            }

            _, created = Property.objects.update_or_create(
                external_id=normalize_label(row.get("record_id", "")),
                defaults=defaults,
            )
            if created:
                stats.properties_created += 1
            else:
                stats.properties_updated += 1

    if rebuild_aggregates:
        built = rebuild_market_snapshots()
        stats.snapshots_built = built["snapshots"]
        stats.segments_built = built["segments"]

    return stats


@transaction.atomic
def rebuild_market_snapshots(as_of_date: date | None = None) -> dict[str, int]:
    as_of_date = as_of_date or _latest_market_date()
    snapshots_built = 0
    segments_built = 0

    for delegation in Delegation.objects.select_related("region").all():
        properties = list(
            Property.objects.filter(delegation=delegation, is_active=True).order_by("id")
        )

        sale_properties = [p for p in properties if p.transaction_type == "sale"]
        rent_properties = [p for p in properties if p.transaction_type == "rent"]
        price_per_sqm_values = [p.price_per_sqm for p in properties if p.price_per_sqm]
        days_on_market = [_days_on_market(p) for p in properties]
        days_on_market = [d for d in days_on_market if d is not None]

        climate = _climate_for_region(delegation.region)
        trend = _trend_for_region(delegation.region)
        population = delegation.population or 0
        supply_pressure = (len(properties) / population * 1000.0) if population else 0.0

        snapshot, _ = DelegationMarketSnapshot.objects.update_or_create(
            delegation=delegation,
            as_of_date=as_of_date,
            defaults={
                "listing_count": len(properties),
                "sale_listing_count": len(sale_properties),
                "rent_listing_count": len(rent_properties),
                "median_sale_price": _safe_median([p.price for p in sale_properties]),
                "median_rent_price": _safe_median([p.price for p in rent_properties]),
                "avg_sale_price": _safe_average([p.price for p in sale_properties]),
                "avg_rent_price": _safe_average([p.price for p in rent_properties]),
                "median_price_per_sqm": _safe_median(price_per_sqm_values),
                "price_per_sqm_distribution": _distribution(price_per_sqm_values),
                "supply_pressure": round(supply_pressure, 4),
                "median_days_on_market": _safe_median(days_on_market),
                "climate_risk_level": climate.flood_risk if climate else "",
                "heat_risk_level": climate.heat_stress_risk if climate else "",
                "sustainability_score": climate.sustainability_score if climate else None,
                "trend_direction": trend.trend_direction if trend else "",
                "forecast_3m": trend.forecast_3m if trend else None,
                "forecast_6m": trend.forecast_6m if trend else None,
                "forecast_12m": trend.forecast_12m if trend else None,
            },
        )
        snapshots_built += 1
        snapshot.segments.all().delete()

        segment_keys = {
            ("all", "sale"),
            ("all", "rent"),
            *{(p.property_type, p.transaction_type) for p in properties},
        }
        for property_type, transaction_type in sorted(segment_keys):
            segment_properties = [
                p
                for p in properties
                if p.transaction_type == transaction_type
                and (property_type == "all" or p.property_type == property_type)
            ]
            if not segment_properties:
                continue

            segment_price_per_sqm = [p.price_per_sqm for p in segment_properties if p.price_per_sqm]
            segment_days_on_market = [_days_on_market(p) for p in segment_properties]
            segment_days_on_market = [d for d in segment_days_on_market if d is not None]
            segment_trend = _trend_for_region(
                delegation.region,
                None if property_type == "all" else property_type,
            )

            DelegationMarketSegment.objects.create(
                snapshot=snapshot,
                property_type=property_type,
                transaction_type=transaction_type,
                listing_count=len(segment_properties),
                median_price=_safe_median([p.price for p in segment_properties]),
                avg_price=_safe_average([p.price for p in segment_properties]),
                median_price_per_sqm=_safe_median(segment_price_per_sqm),
                avg_price_per_sqm=_safe_average(segment_price_per_sqm),
                min_price=min(p.price for p in segment_properties),
                max_price=max(p.price for p in segment_properties),
                avg_surface_sqm=_safe_average([p.area_sqm for p in segment_properties]),
                median_surface_sqm=_safe_median([p.area_sqm for p in segment_properties]),
                median_days_on_market=_safe_median(segment_days_on_market),
                trend_direction=segment_trend.trend_direction if segment_trend else "",
                forecast_3m=segment_trend.forecast_3m if segment_trend else None,
                forecast_6m=segment_trend.forecast_6m if segment_trend else None,
                forecast_12m=segment_trend.forecast_12m if segment_trend else None,
            )
            segments_built += 1

    return {"snapshots": snapshots_built, "segments": segments_built}


def _latest_market_date() -> date:
    latest_scraped = (
        Property.objects.exclude(scraped_at__isnull=True)
        .order_by("-scraped_at")
        .values_list("scraped_at", flat=True)
        .first()
    )
    if latest_scraped:
        return latest_scraped.date()
    return timezone.now().date()
