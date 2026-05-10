"""
core/management/commands/load_climate_data.py

Loads the curated climate risk CSVs from the ClimaTN module into the
core.ClimateRisk and core.Region tables.

Data sources (relative to this repo — adjust DATA_DIR if needed):
  - tunisia_climate_risk_dataset.csv   (24 cities × baseline risk + metadata)
  - city_climate_scores.csv            (computed liveability/sustainability scores)
  - scenario_results.csv               (Baseline / +2°C / +4°C projections)

Usage:
    python manage.py load_climate_data
    python manage.py load_climate_data --csv-dir /custom/path/to/csvs
"""

import csv
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import ClimateRisk, Region
from core.services.climate_intelligence import (
    GOVERNORATE_META,
    compute_risk_score,
    compute_sustainability,
    climate_price_adjustment,
)

logger = logging.getLogger(__name__)

# Default path — the standalone climate risk directory alongside EstateMind
_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[6] / 'climate risk'

# CSV city name → Region.governorate mapping (handles accents + aliases)
_CITY_MAP: dict[str, str] = {
    'tunis':       'Tunis',
    'sfax':        'Sfax',
    'sousse':      'Sousse',
    'kairouan':    'Kairouan',
    'bizerte':     'Bizerte',
    'gabes':       'Gabes',
    'gabès':       'Gabes',
    'ariana':      'Ariana',
    'gafsa':       'Gafsa',
    'monastir':    'Monastir',
    'nabeul':      'Nabeul',
    'hammamet':    'Nabeul',    # Hammamet is in Nabeul governorate
    'béja':        'Beja',
    'beja':        'Beja',
    'jendouba':    'Jendouba',
    'tozeur':      'Tozeur',
    'médenine':    'Medenine',
    'medenine':    'Medenine',
    'tataouine':   'Tataouine',
    'kasserine':   'Kasserine',
    'sidi bouzid': 'Sidi Bouzid',
    'mahdia':      'Mahdia',
    'zaghouan':    'Zaghouan',
    'kebili':      'Kebili',
    'kébili':      'Kebili',
    'ben arous':   'Ben Arous',
    'siliana':     'Siliana',
    'le kef':      'Kef',
    'el kef':      'Kef',
    'kef':         'Kef',
    'manouba':     'Manouba',
    'la manouba':  'Manouba',
}

# Scenario CSV label → field name
_SCENARIO_MAP = {
    'Baseline (Today)': 'scenario_baseline',
    '+2°C Warming':     'scenario_2c',
    '+4°C Warming':     'scenario_4c',
    # tolerant aliases
    '+2C': 'scenario_2c',
    '+4C': 'scenario_4c',
}

_RISK_LEVEL_NORM = {
    'low': 'low', 'medium': 'medium', 'high': 'high',
    'very high': 'very_high', 'very_high': 'very_high',
}


def _norm_city(raw: str) -> str:
    return _CITY_MAP.get(raw.strip().lower(), '')


def _norm_risk(raw: str) -> str:
    return _RISK_LEVEL_NORM.get(raw.strip().lower(), 'medium')


def _safe_float(val) -> float | None:
    if val in (None, '', 'N/A', 'nan', 'NaN'):
        return None
    try:
        return float(str(val).replace(',', '.'))
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    f = _safe_float(val)
    return int(f) if f is not None else None


class Command(BaseCommand):
    help = 'Load ClimaTN climate risk CSV files into core.ClimateRisk (and update Region lat/lon)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-dir',
            type=str,
            default=str(_DEFAULT_DATA_DIR),
            help='Directory containing the three climate CSV files',
        )

    def handle(self, *args, **options):
        data_dir = Path(options['csv_dir'])
        if not data_dir.exists():
            raise CommandError(f'CSV directory not found: {data_dir}')

        baseline_csv  = data_dir / 'tunisia_climate_risk_dataset.csv'
        scores_csv    = data_dir / 'city_climate_scores.csv'
        scenarios_csv = data_dir / 'scenario_results.csv'

        self.stdout.write(self.style.MIGRATE_HEADING('Loading climate risk data...'))

        # --- Pass 1: scenario projections -----------------------------------------
        scenarios: dict[str, dict] = {}
        if scenarios_csv.exists():
            with open(scenarios_csv, encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    gov = _norm_city(row.get('city', ''))
                    if not gov:
                        continue
                    label = row.get('scenario', '').strip()
                    field = _SCENARIO_MAP.get(label)
                    if field:
                        scenarios.setdefault(gov, {})[field] = _safe_float(row.get('sustainability_score'))
            self.stdout.write(f'  Scenarios loaded for {len(scenarios)} governorates.')
        else:
            self.stdout.write(self.style.WARNING(f'  {scenarios_csv.name} not found — skipping scenarios.'))

        # --- Pass 2: computed scores (liveability, sustainability, combined risk) --
        scores: dict[str, dict] = {}
        if scores_csv.exists():
            with open(scores_csv, encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    gov = _norm_city(row.get('city', ''))
                    if not gov:
                        continue
                    scores[gov] = {
                        'livability_score':     _safe_float(row.get('livability_score')),
                        'infrastructure_score': _safe_float(row.get('infrastructure_score')),
                        'sustainability_score_csv': _safe_float(row.get('sustainability_score')),
                        'combined_risk_score':  _safe_float(row.get('combined_risk')),
                        'lat_csv':              _safe_float(row.get('lat')),
                        'lon_csv':              _safe_float(row.get('lon')),
                    }
            self.stdout.write(f'  Computed scores loaded for {len(scores)} governorates.')
        else:
            self.stdout.write(self.style.WARNING(f'  {scores_csv.name} not found — skipping scores.'))

        # --- Pass 3: main dataset (baseline risk levels + climate metrics) ---------
        if not baseline_csv.exists():
            raise CommandError(f'Required file not found: {baseline_csv}')

        created_count  = 0
        updated_count  = 0
        skipped_count  = 0

        with open(baseline_csv, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows   = list(reader)

        with transaction.atomic():
            for row in rows:
                city_raw = row.get('city', '').strip()
                gov_name = _norm_city(city_raw)
                if not gov_name:
                    self.stdout.write(self.style.WARNING(f'  Skipping unknown city: {city_raw!r}'))
                    skipped_count += 1
                    continue

                # Resolve Region FK — create if missing
                region, _ = Region.objects.get_or_create(governorate=gov_name)

                # Update Region lat/lon from dataset
                meta = GOVERNORATE_META.get(gov_name, {})
                lat = _safe_float(row.get('latitude')) or meta.get('lat')
                lon = _safe_float(row.get('longitude')) or meta.get('lon')
                if lat and lon and (region.latitude != lat or region.longitude != lon):
                    region.latitude  = lat
                    region.longitude = lon
                    region.save(update_fields=['latitude', 'longitude'])

                sc = scores.get(gov_name, {})
                sc_scenarios = scenarios.get(gov_name, {})

                # Compute sustainability + risk using our ported algorithms
                sustain_score, sustain_grade = compute_sustainability(gov_name)
                risk_score, risk_category    = compute_risk_score(gov_name)
                adj_pct, _                   = climate_price_adjustment(gov_name)

                # Prefer CSV sustainability score when available (it was computed with live data)
                final_sustain = sc.get('sustainability_score_csv') or sustain_score
                final_grade   = ('A' if final_sustain >= 75 else 'B' if final_sustain >= 60
                                 else 'C' if final_sustain >= 45 else 'D' if final_sustain >= 30 else 'F')
                final_risk    = sc.get('combined_risk_score') or risk_score

                defaults = {
                    # Risk levels (categorical)
                    'flood_risk':      _norm_risk(row.get('flood_risk_level', 'Medium')),
                    'heat_stress_risk': _norm_risk(row.get('heat_risk_level', 'Medium')),
                    'drought_risk':    _norm_risk(row.get('drought_risk_level', 'Medium')),
                    'earthquake_risk': _norm_risk(row.get('earthquake_risk_level', 'Low')),
                    # Numeric risk scores from dataset (0–10 scale)
                    'flood_risk_score':      _safe_float(row.get('flood_risk_score')),
                    'heat_risk_score':       _safe_float(row.get('heat_risk_score')),
                    'drought_risk_score':    _safe_float(row.get('drought_risk_score')),
                    'earthquake_risk_score': _safe_float(row.get('earthquake_risk_score')),
                    # Composite
                    'combined_risk_score': final_risk,
                    'risk_category':       row.get('overall_risk_category', risk_category).strip() or risk_category,
                    # Sustainability
                    'sustainability_score': final_sustain,
                    'sustainability_grade': final_grade,
                    'livability_score':     sc.get('livability_score'),
                    'infrastructure_score': sc.get('infrastructure_score'),
                    # Geospatial
                    'lat':            lat,
                    'lon':            lon,
                    'is_coastal':     str(row.get('is_coastal', 'No')).strip().lower() in ('yes', 'true', '1'),
                    'climate_region': meta.get('region', ''),
                    # Climate baseline
                    'avg_temp_c':         _safe_float(row.get('avg_annual_temp_c')),
                    'max_summer_temp_c':  _safe_float(row.get('max_summer_temp_c')),
                    'avg_rainfall_mm':    _safe_float(row.get('avg_annual_rainfall_mm')),
                    'days_above_35c':     _safe_int(row.get('days_above_35c_per_year')),
                    'sea_level_exposure': str(row.get('sea_level_rise_exposure', '')).strip()[:10],
                    # Price impact
                    'price_adjustment_pct': adj_pct,
                    # Scenarios
                    'scenario_baseline': sc_scenarios.get('scenario_baseline'),
                    'scenario_2c':       sc_scenarios.get('scenario_2c'),
                    'scenario_4c':       sc_scenarios.get('scenario_4c'),
                }

                obj, created = ClimateRisk.objects.update_or_create(
                    region=region, defaults=defaults,
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

        # Fill any remaining governorates not in the CSV using computed values
        filled = 0
        for gov_name, meta in GOVERNORATE_META.items():
            region, _ = Region.objects.get_or_create(governorate=gov_name)
            if not ClimateRisk.objects.filter(region=region).exists():
                s, g   = compute_sustainability(gov_name)
                rs, rc = compute_risk_score(gov_name)
                ap, _  = climate_price_adjustment(gov_name)
                ClimateRisk.objects.create(
                    region=region,
                    flood_risk=_norm_risk(GOVERNORATE_META[gov_name].get('flood', 'medium')),
                    heat_stress_risk='medium',
                    drought_risk='medium',
                    earthquake_risk='low',
                    combined_risk_score=rs,
                    risk_category=rc,
                    sustainability_score=s,
                    sustainability_grade=g,
                    lat=meta['lat'],
                    lon=meta['lon'],
                    is_coastal=meta['coastal'],
                    climate_region=meta['region'],
                    price_adjustment_pct=ap,
                )
                filled += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nClimate data loaded: {created_count} created, {updated_count} updated, '
            f'{filled} computed from algorithm, {skipped_count} skipped.'
        ))
