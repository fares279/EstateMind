"""
Generate 12-month price forecasts from delegations.csv (compound-growth method).

For each delegation × property type, applies compound monthly growth derived
from the CSV annual trend to produce Jan–Dec 2026 forecasts.

Result: 278 delegations × 4 types × 12 months = 13,344 DelegationForecast rows
        278 delegations × 4 types              =  1,112 DelegationPriceData rows

Run:
    python manage.py generate_forecasts
"""
import csv
import logging
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# delegations.csv lives two levels above the outer EstateMind directory
CSV_PATH = Path(__file__).resolve().parents[5] / 'delegations' / 'delegations.csv'

FORECAST_ORIGIN = date(2026, 1, 1)

PROPERTY_CONFIG = {
    'apartment': {
        'avg': 'Apartment_Avg_TND', 'min': 'Apartment_Min_TND',
        'max': 'Apartment_Max_TND', 'trend': 'Apartment_Trend_Percent',
        'notes': 'Apartment_Notes',
    },
    'house': {
        'avg': 'House_Avg_TND', 'min': 'House_Min_TND',
        'max': 'House_Max_TND', 'trend': 'House_Trend_Percent',
        'notes': 'House_Notes',
    },
    'commercial': {
        'avg': 'Commercial_Avg_TND', 'min': 'Commercial_Min_TND',
        'max': 'Commercial_Max_TND', 'trend': 'Commercial_Trend_Percent',
        'notes': 'Commercial_Notes',
    },
    'land': {
        'avg': 'Land_Avg_TND', 'min': 'Land_Min_TND',
        'max': 'Land_Max_TND', 'trend': 'Land_Trend_Percent',
        'notes': 'Land_Notes',
    },
}


def _add_months(d, n):
    total = d.month - 1 + n
    return date(d.year + total // 12, total % 12 + 1, 1)


def _parse_trend(raw):
    s = str(raw).strip().rstrip('%').replace('+', '')
    try:
        return float(s)
    except ValueError:
        return 0.0


class Command(BaseCommand):
    help = 'Regenerate DelegationForecast + DelegationPriceData from delegations.csv (idempotent).'

    def handle(self, *args, **options):
        from forecast.models import DelegationForecast, DelegationPriceData

        if not CSV_PATH.exists():
            self.stderr.write(self.style.ERROR(f'CSV not found: {CSV_PATH}'))
            return

        price_rows    = []
        forecast_rows = []
        skipped       = 0

        with open(CSV_PATH, newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                delegation  = row.get('Delegation',  '').strip()
                governorate = row.get('Governorate', '').strip()
                if not delegation or not governorate:
                    continue

                for prop_type, cols in PROPERTY_CONFIG.items():
                    try:
                        price_avg        = float(row[cols['avg']])
                        price_min        = float(row[cols['min']])
                        price_max        = float(row[cols['max']])
                        annual_trend_pct = _parse_trend(row[cols['trend']])
                        notes            = row.get(cols['notes'], '')
                    except (ValueError, KeyError):
                        skipped += 1
                        continue

                    price_rows.append(DelegationPriceData(
                        delegation_name=delegation,
                        governorate=governorate,
                        property_type=prop_type,
                        price_min=price_min,
                        price_avg=price_avg,
                        price_max=price_max,
                        annual_trend_pct=annual_trend_pct,
                        notes=notes,
                    ))

                    # h=1 → Jan 2026 base price (no growth yet)
                    # h=12 → Dec 2026 after 11 months of compound growth
                    monthly_factor = (1 + annual_trend_pct / 100) ** (1 / 12)
                    for h in range(1, 13):
                        price_tnd = price_avg * (monthly_factor ** (h - 1))
                        forecast_rows.append(DelegationForecast(
                            delegation_name=delegation,
                            governorate=governorate,
                            property_type=prop_type,
                            forecast_origin=FORECAST_ORIGIN,
                            forecast_month=_add_months(FORECAST_ORIGIN, h - 1),
                            horizon_idx=h,
                            predicted_price_per_m2=price_tnd * 1000,  # store in millimes
                            model_mape_pct=2.50,
                            model_version='csv_v2',
                        ))

        self.stdout.write(
            f'Parsed {len(price_rows)} price rows, {len(forecast_rows)} forecast rows'
            + (f', {skipped} skipped' if skipped else '') + '.'
        )

        self.stdout.write('Clearing old data…')
        DelegationPriceData.objects.all().delete()
        DelegationForecast.objects.all().delete()

        self.stdout.write('Inserting DelegationPriceData…')
        DelegationPriceData.objects.bulk_create(price_rows, batch_size=500)

        self.stdout.write('Inserting DelegationForecast…')
        DelegationForecast.objects.bulk_create(forecast_rows, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f'Done — {len(price_rows)} price rows + {len(forecast_rows)} forecast rows written.'
        ))
