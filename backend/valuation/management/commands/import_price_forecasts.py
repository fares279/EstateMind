"""
Management command: import 12-month price forecasts from the ML pipeline artefact.
Run: python manage.py import_price_forecasts [--dry-run]
"""
import csv
import logging
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parents[5] / "Price-Trend-Forecasting"
FORECAST_CSV    = _BASE / "forecast_only_artifacts_h12" / "forecast_table_h12.csv"
DELEGATIONS_CSV = _BASE / "delegations.csv"


def _norm(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower().strip()


def _build_gov_map():
    mapping = {}
    if not DELEGATIONS_CSV.exists():
        logger.warning("delegations.csv not found at %s", DELEGATIONS_CSV)
        return mapping
    with open(DELEGATIONS_CSV, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            d = row.get("Delegation", "").strip()
            g = row.get("Governorate", "").strip()
            if d and g:
                mapping[_norm(d)] = g
    return mapping


class Command(BaseCommand):
    help = "Seed DelegationForecast table from ML forecast CSV (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from valuation.models import DelegationForecast
        from core.models import Delegation

        dry_run = options["dry_run"]

        if not FORECAST_CSV.exists():
            self.stderr.write(self.style.ERROR(f"Forecast CSV not found: {FORECAST_CSV}"))
            return

        gov_map   = _build_gov_map()
        del_cache = {}

        def _resolve_delegation(name):
            key = _norm(name)
            if key in del_cache:
                return del_cache[key]
            obj = (Delegation.objects.filter(name__iexact=name).first()
                   or Delegation.objects.filter(name__icontains=name).first())
            del_cache[key] = obj
            return obj

        rows_to_upsert = []
        with open(FORECAST_CSV, newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                delegation_name = row["delegation_id"].strip()
                try:
                    price_mm = float(row["predicted_price_per_m2"])
                    horizon  = int(row["horizon_idx"])
                    origin   = row["forecast_origin_month"][:10]
                    month    = row["forecast_month"][:10]
                except (KeyError, ValueError) as exc:
                    logger.warning("Skipping bad row %s: %s", row, exc)
                    continue
                governorate   = gov_map.get(_norm(delegation_name), "")
                delegation_fk = _resolve_delegation(delegation_name) if not dry_run else None
                rows_to_upsert.append(DelegationForecast(
                    delegation_name        = delegation_name,
                    governorate            = governorate,
                    delegation_fk          = delegation_fk,
                    forecast_origin        = origin,
                    forecast_month         = month,
                    horizon_idx            = horizon,
                    predicted_price_per_m2 = price_mm,
                    model_mape_pct         = 2.92,
                    model_version          = "h12_v1",
                ))

        self.stdout.write(f"Parsed {len(rows_to_upsert)} forecast rows.")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no DB writes."))
            return

        DelegationForecast.objects.bulk_create(
            rows_to_upsert,
            update_conflicts=True,
            unique_fields=["delegation_name", "forecast_origin", "horizon_idx"],
            update_fields=[
                "governorate", "delegation_fk", "forecast_month",
                "predicted_price_per_m2", "model_mape_pct", "model_version",
            ],
        )
        self.stdout.write(self.style.SUCCESS(
            f"Imported/updated {len(rows_to_upsert)} forecast rows."
        ))


