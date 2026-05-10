"""
management command: import_delegations

Reads backend/data/delegations.csv and upserts Region + Delegation records
including all market-benchmark price fields (TND/m²).

Usage:
    python manage.py import_delegations
    python manage.py import_delegations --csv /path/to/custom.csv
"""
import csv
import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import Delegation, Region

logger = logging.getLogger(__name__)

_DEFAULT_CSV = Path(__file__).resolve().parents[3] / "data" / "delegations.csv"

COASTAL_GOVS = {
    "Tunis", "Ariana", "Ben Arous", "Manouba",
    "Nabeul", "Zaghouan", "Bizerte", "Beja",
    "Jendouba", "Sfax", "Mahdia", "Monastir",
    "Sousse", "Gabes", "Medenine",
}


def _pct(raw: str) -> float | None:
    if not raw:
        return None
    try:
        return float(raw.strip().replace("−", "-").replace("%", "")) / 100.0
    except ValueError:
        return None


def _flt(raw: str) -> float | None:
    if not raw:
        return None
    try:
        return float(raw.strip().replace(",", ""))
    except ValueError:
        return None


def _int(raw: str) -> int:
    try:
        return int(raw.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return 0


class Command(BaseCommand):
    help = "Import delegation price benchmarks from backend/data/delegations.csv into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            default=None,
            help="Path to delegations CSV (default: backend/data/delegations.csv)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate the CSV without writing to the database.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"]) if options["csv_path"] else _DEFAULT_CSV
        dry_run = options["dry_run"]

        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
            return

        self.stdout.write(f"Reading: {csv_path}")

        rows = []
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            for raw in csv.DictReader(fh):
                delegation_name = raw.get("Delegation", "").strip()
                governorate     = raw.get("Governorate", "").strip()
                if not delegation_name or not governorate:
                    continue
                rows.append({
                    "delegation":       delegation_name,
                    "governorate":      governorate,
                    "population":       _int(raw.get("Population_2024", "0")),
                    "is_coastal":       governorate in COASTAL_GOVS,
                    "apt_min_tnd":      _flt(raw.get("Apartment_Min_TND")),
                    "apt_avg_tnd":      _flt(raw.get("Apartment_Avg_TND")),
                    "apt_max_tnd":      _flt(raw.get("Apartment_Max_TND")),
                    "apt_trend_pct":    _pct(raw.get("Apartment_Trend_Percent")),
                    "house_min_tnd":    _flt(raw.get("House_Min_TND")),
                    "house_avg_tnd":    _flt(raw.get("House_Avg_TND")),
                    "house_max_tnd":    _flt(raw.get("House_Max_TND")),
                    "house_trend_pct":  _pct(raw.get("House_Trend_Percent")),
                    "comm_min_tnd":     _flt(raw.get("Commercial_Min_TND")),
                    "comm_avg_tnd":     _flt(raw.get("Commercial_Avg_TND")),
                    "comm_max_tnd":     _flt(raw.get("Commercial_Max_TND")),
                    "comm_trend_pct":   _pct(raw.get("Commercial_Trend_Percent")),
                    "land_min_tnd":     _flt(raw.get("Land_Min_TND")),
                    "land_avg_tnd":     _flt(raw.get("Land_Avg_TND")),
                    "land_max_tnd":     _flt(raw.get("Land_Max_TND")),
                    "land_trend_pct":   _pct(raw.get("Land_Trend_Percent")),
                })

        self.stdout.write(f"Parsed {len(rows)} delegation rows.")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no database writes."))
            for r in rows[:5]:
                self.stdout.write(f"  {r['delegation']} ({r['governorate']}) apt_avg={r['apt_avg_tnd']}")
            return

        regions_created = regions_updated = 0
        delegations_created = delegations_updated = 0

        for row in rows:
            gov = row["governorate"]
            region, r_created = Region.objects.update_or_create(
                governorate=gov,
                defaults={"population": row["population"] if row["population"] else None},
            )
            if r_created:
                regions_created += 1
            else:
                regions_updated += 1

            _, d_created = Delegation.objects.update_or_create(
                region=region,
                name=row["delegation"],
                defaults={
                    "population":    row["population"],
                    "is_coastal":    row["is_coastal"],
                    "apt_min_tnd":   row["apt_min_tnd"],
                    "apt_avg_tnd":   row["apt_avg_tnd"],
                    "apt_max_tnd":   row["apt_max_tnd"],
                    "apt_trend_pct": row["apt_trend_pct"],
                    "house_min_tnd":   row["house_min_tnd"],
                    "house_avg_tnd":   row["house_avg_tnd"],
                    "house_max_tnd":   row["house_max_tnd"],
                    "house_trend_pct": row["house_trend_pct"],
                    "comm_min_tnd":    row["comm_min_tnd"],
                    "comm_avg_tnd":    row["comm_avg_tnd"],
                    "comm_max_tnd":    row["comm_max_tnd"],
                    "comm_trend_pct":  row["comm_trend_pct"],
                    "land_min_tnd":    row["land_min_tnd"],
                    "land_avg_tnd":    row["land_avg_tnd"],
                    "land_max_tnd":    row["land_max_tnd"],
                    "land_trend_pct":  row["land_trend_pct"],
                },
            )
            if d_created:
                delegations_created += 1
            else:
                delegations_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done — regions: {regions_created} created / {regions_updated} updated | "
            f"delegations: {delegations_created} created / {delegations_updated} updated"
        ))
