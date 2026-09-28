"""
Populate a working database from the reference data in the repository.

    python manage.py seed_demo_data [--synthetic-per-type 3] [--no-synthetic] [--seed 42]

Idempotent: re-running updates the same rows (fixed ids, fixed random seed).

What is loaded, and from where:
  1. Regions (24) and delegations (278) from data/delegations.csv, with coordinates and
     coastal flags from data/delegation_geography.csv / governorate_geography.csv.
     Those geography files were exported from the original EstateMind database; coastal
     flags are kept as they were there (a known issue awaiting domain review).
  2. Real listings from the valuation listings.csv, cleaned with the same rules as the
     model training data (ml/shared/listings_dataset.py, location 'v2', generated-looking
     rows removed). Property.source = 'listings_csv', external_id 'listings-<record_id>'.
     Positions are delegation centroids: the listings' own coordinates are unreliable.
  3. Synthetic sample listings, only for a delegation + property type with no real
     sale listing: price per m2 drawn between the delegation's min/avg/max benchmarks,
     surface/rooms taken from a real listing of the same type. Property.source =
     'synthetic', external_id 'synthetic-...', title and description say so.
     No synthetic rents are generated (there is no rent benchmark to draw from).
  4. Market snapshots per delegation (core.data_pipeline.rebuild_market_snapshots),
     which record how many real and synthetic listings each is built from.
  5. Price forecasts (generate_forecasts), delegation climate scores
     (seed_climate_scores), and the daily dashboard summaries (normally Celery beat).
"""
from __future__ import annotations

import csv
import random

import pandas as pd
from django.core.management import BaseCommand, call_command
from django.db import transaction

from config.paths import DATA_DIR

SOURCE_REAL = 'listings_csv'
TYPE_MAP = {'appartement': 'apartment', 'maison': 'house', 'terrain': 'land',
            'Appartement': 'apartment', 'Maison': 'house', 'Terrain': 'land'}
TYPE_LABEL = {'apartment': 'Apartment', 'house': 'House', 'land': 'Land'}
BENCHMARK = {'apartment': 'apt', 'house': 'house', 'land': 'land'}
RENT_RANGE = (150, 15_000)          # TND per month
RENT_PPM_RANGE = (1, 100)           # TND per m2 per month


class Command(BaseCommand):
    help = 'Seed regions, delegations, listings (real + labelled synthetic), snapshots, forecasts, climate scores.'

    def add_arguments(self, parser):
        parser.add_argument('--synthetic-per-type', type=int, default=3)
        parser.add_argument('--no-synthetic', action='store_true')
        parser.add_argument('--seed', type=int, default=42)

    def handle(self, *args, **opts):
        self.rng = random.Random(opts['seed'])
        with transaction.atomic():
            regions, delegations = self._geography()
            real = self._real_listings(regions, delegations)
            synthetic = 0 if opts['no_synthetic'] else self._synthetic(delegations, opts['synthetic_per_type'])
            # forecasts first: snapshots take their trend fields from them
            call_command('generate_forecasts', stdout=self.stdout)
            from estatemind.market.core.data_pipeline import rebuild_market_snapshots
            built = rebuild_market_snapshots()
        self.stdout.write(f'Snapshots: {built["snapshots"]} delegations, {built["segments"]} segments')
        call_command('seed_climate_scores', force=True, stdout=_Quiet())
        from estatemind.market.core.models import DelegationClimateScore
        self.stdout.write(f'Climate scores: {DelegationClimateScore.objects.count()} delegations')
        # The daily summaries the dashboards read are normally built by Celery beat,
        # which does not run in local development: build them once now.
        from estatemind.intelligence.forecast.tasks import materialize_daily_forecast_summary
        from estatemind.intelligence.investor.tasks import materialize_daily_investor_summary
        from estatemind.market.core.tasks import materialize_daily_market_analytics
        for task in (materialize_daily_market_analytics, materialize_daily_forecast_summary,
                     materialize_daily_investor_summary):
            self.stdout.write(f'{task.name}: {task()}')
        # register the valuation models that artifact discovery serves (never promotes a challenger)
        from estatemind.intelligence.valuation.tasks import sync_registry_from_artifacts
        self.stdout.write(f'valuation registry sync: {sync_registry_from_artifacts()}')
        self.stdout.write(self.style.SUCCESS(
            f'Done: {len(regions)} regions, {len(delegations)} delegations, {real} real listings, '
            f'{synthetic} synthetic listings (Property.source="synthetic").'))

    # ── 1. regions + delegations ─────────────────────────────────────────────
    def _geography(self):
        from estatemind.intelligence.valuation.inference.location import normalize_governorate, plain
        from estatemind.market.core.management.commands.import_delegations import _flt, _int, _pct
        from estatemind.market.core.models import Delegation, Region

        gov_geo = {r['governorate_key']: r for r in csv.DictReader(open(DATA_DIR / 'governorate_geography.csv',
                                                                          encoding='utf-8'))}
        del_geo = {(plain(r['delegation']), normalize_governorate(r['governorate'])): r
                   for r in csv.DictReader(open(DATA_DIR / 'delegation_geography.csv', encoding='utf-8'))}
        rows = list(csv.DictReader(open(DATA_DIR / 'delegations.csv', encoding='utf-8-sig')))

        population = {}
        for r in rows:
            population[r['Governorate']] = population.get(r['Governorate'], 0) + _int(r['Population_2024'])

        regions = {}
        for name, pop in population.items():
            key = normalize_governorate(name)
            geo = gov_geo.get(key, {})
            region, _ = Region.objects.update_or_create(governorate=name, defaults={
                'population': pop,
                'latitude': float(geo['latitude']) if geo.get('latitude') else None,
                'longitude': float(geo['longitude']) if geo.get('longitude') else None,
            })
            regions[key] = region

        delegations = {}
        for r in rows:
            gov_key = normalize_governorate(r['Governorate'])
            geo = del_geo.get((plain(r['Delegation']), gov_key), {})
            fields = {
                'population': _int(r['Population_2024']),
                'centroid_lat': float(geo['latitude']) if geo.get('latitude') else None,
                'centroid_lon': float(geo['longitude']) if geo.get('longitude') else None,
                'is_coastal': geo.get('is_coastal') == '1',
            }
            for prefix, col in (('apt', 'Apartment'), ('house', 'House'), ('comm', 'Commercial'), ('land', 'Land')):
                fields[f'{prefix}_min_tnd'] = _flt(r[f'{col}_Min_TND'])
                fields[f'{prefix}_avg_tnd'] = _flt(r[f'{col}_Avg_TND'])
                fields[f'{prefix}_max_tnd'] = _flt(r[f'{col}_Max_TND'])
                fields[f'{prefix}_trend_pct'] = _pct(r[f'{col}_Trend_Percent'])
            delegation, _ = Delegation.objects.update_or_create(region=regions[gov_key], name=r['Delegation'],
                                                                defaults=fields)
            delegations[(plain(r['Delegation']), gov_key)] = delegation
        self.stdout.write(f'Geography: {len(regions)} regions, {len(delegations)} delegations '
                          f'({sum(1 for d in delegations.values() if d.centroid_lat is None)} without coordinates)')
        return regions, delegations

    # ── 2. real listings ─────────────────────────────────────────────────────
    def _real_listings(self, regions, delegations) -> int:
        from ml.shared.listings_dataset import Options, build
        from estatemind.market.core.models import Property

        sales = build(options=Options(location='v2', drop_cross_town_duplicates=True, drop_fractional_surfaces=True))
        sale_rows = pd.concat([sales.train, sales.test])
        rent_rows = self._rent_rows()
        self._surface_pool = {TYPE_MAP[t]: part[['surface_m2', 'bedrooms', 'bathrooms']].to_dict('records')
                              for t, part in sale_rows.groupby('property_type')}

        seen, matched = set(), 0
        for tx, frame in (('sale', sale_rows), ('rent', rent_rows)):
            for r in frame.itertuples(index=False):
                ptype = TYPE_MAP.get(r.property_type)
                region = regions.get(r.governorate)
                if ptype is None or region is None:
                    continue
                delegation = delegations.get((r.city, r.governorate))
                matched += delegation is not None
                place = delegation.name if delegation else region.governorate
                lat = (delegation.centroid_lat if delegation and delegation.centroid_lat else region.latitude)
                lon = (delegation.centroid_lon if delegation and delegation.centroid_lon else region.longitude)
                external_id = f'listings-{r.record_id}'
                seen.add(external_id)
                Property.objects.update_or_create(external_id=external_id, defaults={
                    'title': f"{TYPE_LABEL[ptype]} {'for sale' if tx == 'sale' else 'for rent'} in {place}",
                    'description': str(r.description or ''),
                    'property_type': ptype, 'transaction_type': tx,
                    'region': region, 'delegation': delegation,
                    'price': float(r.price_tnd), 'area_sqm': float(r.surface_m2),
                    'price_per_sqm': round(float(r.price_tnd) / float(r.surface_m2), 2),
                    # the listing's own room count (training uses a derived one)
                    'rooms': _int_or_none(getattr(r, 'rooms_listed', r.rooms)),
                    'bedrooms': _int_or_none(r.bedrooms),
                    'bathrooms': _int_or_none(r.bathrooms),
                    'latitude': lat, 'longitude': lon, 'geocoding_precision': 'centroid',
                    'location_raw': str(r.city_raw or ''), 'source': SOURCE_REAL, 'is_active': True,
                })
        Property.objects.filter(source=SOURCE_REAL).exclude(external_id__in=seen).delete()
        self.stdout.write(f'Real listings: {len(seen)} ({len(sale_rows)} sale, {len(rent_rows)} rent), '
                          f'{matched} matched to a delegation, the rest to their governorate only')
        return len(seen)

    def _rent_rows(self) -> pd.DataFrame:
        """Rental listings, cleaned like the sales: plausible rent and surface, per-row
        location rules, duplicates and decimal surfaces removed."""
        from ml.shared.listings_dataset import LISTINGS_CSV, SURFACE_RANGE, derive_location
        raw = pd.read_csv(LISTINGS_CSV)
        df = raw[(raw['transaction_type'] == 'rent') & raw['property_type'].isin(['Appartement', 'Maison'])].copy()
        df['property_type'] = df['property_type'].map({'Appartement': 'appartement', 'Maison': 'maison'})
        lo = df['property_type'].map(lambda t: SURFACE_RANGE[t][0])
        hi = df['property_type'].map(lambda t: SURFACE_RANGE[t][1])
        ppm = df['price_tnd'] / df['surface_m2']
        df = df[df['price_tnd'].between(*RENT_RANGE) & df['surface_m2'].between(lo, hi) & ppm.between(*RENT_PPM_RANGE)
                & (df['surface_m2'] % 1 == 0)]
        df = df.drop_duplicates(subset=['property_type', 'price_tnd', 'surface_m2', 'city', 'bedrooms'])
        derived = [derive_location(g, c) for g, c in zip(df['governorate'], df['city'])]
        df = df.assign(city_raw=df['city'], governorate=[d[0] for d in derived],
                       city=[d[1] or d[0] for d in derived])
        return df

    # ── 3. synthetic listings ────────────────────────────────────────────────
    def _synthetic(self, delegations, per_type: int) -> int:
        from estatemind.market.core.models import SYNTHETIC_SOURCE, Property
        from ml.shared.listings_dataset import PRICE_RANGE

        real_types = set(Property.objects.filter(source=SOURCE_REAL, transaction_type='sale', delegation__isnull=False)
                         .values_list('delegation_id', 'property_type'))
        made = set()
        for delegation in sorted(delegations.values(), key=lambda d: d.id):
            for ptype, prefix in BENCHMARK.items():
                if (delegation.id, ptype) in real_types:
                    continue
                lo, mid, hi = (getattr(delegation, f'{prefix}_{k}_tnd') for k in ('min', 'avg', 'max'))
                if not mid:
                    continue
                lo, hi = lo or mid * 0.8, hi or mid * 1.2
                for i in range(per_type):
                    # same plausibility rule as the real listings (PRICE_RANGE); redraw otherwise
                    for _attempt in range(20):
                        ppm = self.rng.triangular(min(lo, mid), max(hi, mid), mid)
                        shape = self.rng.choice(self._surface_pool[ptype])
                        surface = float(shape['surface_m2'])
                        price = round(ppm * surface, -3)
                        if PRICE_RANGE[0] <= price <= PRICE_RANGE[1]:
                            break
                    else:
                        continue
                    external_id = f'synthetic-{delegation.id}-{ptype}-{i}'
                    made.add(external_id)
                    Property.objects.update_or_create(external_id=external_id, defaults={
                        'title': f'Sample {TYPE_LABEL[ptype].lower()} in {delegation.name} (synthetic)',
                        'description': (f"Synthetic example generated from EstateMind's price benchmarks for "
                                        f"{delegation.name}, {delegation.region.governorate}. Not a real listing."),
                        'property_type': ptype, 'transaction_type': 'sale',
                        'region': delegation.region, 'delegation': delegation,
                        'price': price, 'area_sqm': surface, 'price_per_sqm': round(price / surface, 2),
                        'rooms': (int(shape['bedrooms']) + 1) if ptype != 'land' else 0,
                        'bedrooms': int(shape['bedrooms']), 'bathrooms': int(shape['bathrooms']),
                        'latitude': delegation.centroid_lat or delegation.region.latitude,
                        'longitude': delegation.centroid_lon or delegation.region.longitude,
                        'geocoding_precision': 'centroid', 'source': SYNTHETIC_SOURCE, 'is_active': True,
                    })
        Property.objects.filter(source=SYNTHETIC_SOURCE).exclude(external_id__in=made).delete()
        self.stdout.write(f'Synthetic listings: {len(made)} (only where a delegation has no real sale listing '
                          f'of that type)')
        return len(made)


def _int_or_none(value):
    return None if value is None or value != value else int(value)


class _Quiet:
    def write(self, *_args, **_kwargs):
        pass

    def flush(self):
        pass
