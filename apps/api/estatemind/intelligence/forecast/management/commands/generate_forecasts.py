"""
Generate 12-month price outlooks: the reference price of delegations.csv, grown at the
national rate of the INS property price index plus the delegation's local deviation.

For each delegation × property type, the annual growth is
    national expected growth of the type (forecast/services/national_index.py: the
    INS index's average growth since 2000, the best of five methods in a backtest
    from 2005)
  + the delegation's benchmark trend minus the median benchmark trend of the type
    (most benchmark trends are 0%, so most delegations get the national rate),
compounded monthly over the 12 months starting with the current month.
model_mape_pct records the national backtest's mean absolute error of 12-month growth
(percentage points); local accuracy is not measured (no delegation price history).
The outlook used to apply the benchmark trend alone (mostly 0%), which had the largest
error in that backtest.

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

from config.paths import DATA_DIR, EXTERNAL_DATA_DIR

# The copy in the repo (data/delegations.csv); the external folder the original
# backend read from is not part of this repository.
CSV_PATH = DATA_DIR / 'delegations.csv'
if not CSV_PATH.exists():
    CSV_PATH = EXTERNAL_DATA_DIR / 'delegations' / 'delegations.csv'

FORECAST_ORIGIN = date.today().replace(day=1)  # series starts at the current month

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
        from estatemind.intelligence.forecast.models import DelegationForecast, DelegationPriceData

        if not CSV_PATH.exists():
            self.stderr.write(self.style.ERROR(f'CSV not found: {CSV_PATH}'))
            return

        from statistics import median

        from estatemind.intelligence.forecast.services import national_index

        price_rows    = []
        forecast_rows = []
        skipped       = 0

        with open(CSV_PATH, newline='', encoding='utf-8-sig') as f:
            csv_rows = list(csv.DictReader(f))
        national = {t: national_index.expected_annual_growth_pct(t) for t in PROPERTY_CONFIG}
        national_mae = {t: national_index.backtest(t)['mae_12m_pp'][national_index.CHOSEN] for t in PROPERTY_CONFIG}
        typical_trend = {t: median(_parse_trend(r.get(c['trend'], '')) for r in csv_rows)
                         for t, c in PROPERTY_CONFIG.items()}
        for row in csv_rows:
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

                # h=1 → current month (benchmark price); h=12 → 11 months of compound growth later
                growth_pct = national[prop_type] + annual_trend_pct - typical_trend[prop_type]
                monthly_factor = (1 + growth_pct / 100) ** (1 / 12)
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
                        model_mape_pct=national_mae[prop_type],
                        model_version='ins_national_trend',
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
