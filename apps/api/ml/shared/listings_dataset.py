"""Sale-listings dataset for training the served valuation models.

Rebuilds, from valuation/data/listings.csv, the 14 features the CatBoost
serving bundles use (the original preprocessing project is lost):

    transaction_type, property_type, surface_m2, rooms, bedrooms, bathrooms,
    governorate, city, latitude, longitude, city_governorate,
    local_avg_price_m2, gov_avg_price_m2, size_x_local_price
    target: log1p(price_tnd)

Cleaning rules, in order (each one is counted in the data card):
  1. sale listings of Appartement / Maison / Terrain only
  2. plausible price: 20,000 - 5,000,000 TND
  3. plausible surface: appartement 20-600 m2, maison 40-3,000 m2, terrain 50-100,000 m2
  4. plausible price per m2: appartement/maison 200-15,000 TND, terrain 5-8,000 TND
  5. duplicates (same type, price, surface, city, coordinates, rooms) keep one row
Descriptions are not used: every listing's description in listings.csv is
generated from its title ("Informations déduites automatiquement..."), and
3,293 rows share one identical text, so they carry no information.
rooms: derived as bedrooms + 1 (land: bedrooms), as the serving request
mapper does; the listed room count is kept as rooms_listed, unused.
Location: governorate/city normalized with inference.location (v1), the
same function serving applies to models trained here.
Split: 80/20 per property type, fixed seed; duplicates are removed first, so
a re-posted listing cannot be on both sides.
Priors: median price per m2 by city__governorate (min 3 listings), by
governorate (min 3), and overall, per property type, computed on the
training split only, then applied to both splits.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from estatemind.intelligence.valuation.inference.location import (
    LOCATION_NORMALIZATION, normalize_city, normalize_governorate, plain,
)

LISTINGS_CSV = Path(__file__).resolve().parents[2] / 'estatemind' / 'intelligence' / 'valuation' / 'data' / 'listings.csv'

TYPES = {'Appartement': 'appartement', 'Maison': 'maison', 'Terrain': 'terrain'}
PRICE_RANGE = (20_000, 5_000_000)
SURFACE_RANGE = {'appartement': (20, 600), 'maison': (40, 3_000), 'terrain': (50, 100_000)}
PPM_RANGE = {'appartement': (200, 15_000), 'maison': (200, 15_000), 'terrain': (5, 8_000)}
PRIOR_MIN_COUNT = 3
TEST_SHARE = 0.20
SEED = 42

FEATURES = ['transaction_type', 'property_type', 'surface_m2', 'rooms', 'bedrooms', 'bathrooms', 'governorate',
            'city', 'latitude', 'longitude', 'city_governorate', 'local_avg_price_m2', 'gov_avg_price_m2',
            'size_x_local_price']
CATEGORICAL = ['transaction_type', 'property_type', 'governorate', 'city', 'city_governorate']

# Scraper default for listings it could not geocode: the geographic centre of
# Tunisia. 23% of listings.csv sits exactly here.
COUNTRY_CENTROID = (33.8439408, 9.400138)


@dataclass(frozen=True)
class Options:
    """Cleaning choices. The defaults rebuild the v2 (estate_v2_20260927) data exactly.

    location: 'v1' reads governorate/city as labelled. 'v2' decides per row
        which column holds the town (see derive_location): the columns are
        swapped in most rows, but not all.
    drop_cross_town_duplicates: drop listings whose exact (type, price, surface)
        appears in more than one town: filled-in values, not listings.
    drop_fractional_surfaces: drop surfaces with decimals (a 2-room flat at
        217.4 m2): generated upstream, not scraped.
    coordinates: 'keep'; 'centroid_missing' blanks the not-geocoded default;
        'none' blanks all coordinates (serving never receives any).
    holdout_ids: record_ids forced into the test split, so models built with
        different options are compared on the same unseen listings.
    """
    location: str = 'v1'
    drop_cross_town_duplicates: bool = False
    drop_fractional_surfaces: bool = False
    coordinates: str = 'keep'
    holdout_ids: frozenset | None = None


V1 = Options()


def _governorate_names() -> set[str]:
    from estatemind.intelligence.valuation.inference.location import _reference
    return set(_reference()[0])


def _town(text) -> str | None:
    """Town from a location string: 'Borj Louzir à La Soukra' -> 'la soukra',
    "L'Aouina, La Marsa, Tunis" -> 'la marsa'. None for 'Autres villes' or a
    governorate name (no town given)."""
    text = str(text or '')
    if ' à ' in text:
        text = text.rsplit(' à ', 1)[1]
    elif ',' in text:
        govs = _governorate_names()
        parts = [p for p in text.split(',') if plain(p) and plain(p) not in govs]
        text = parts[-1] if parts else ''
    town = plain(text)
    if not town or town in ('autres villes', 'grand tunis') or town in _governorate_names():
        return None
    return town


def derive_location(governorate_col, city_col) -> tuple[str, str | None, str]:
    """(governorate, town or None, pattern) for one listing, by which column
    holds a governorate name. Counted per pattern in the data card."""
    govs = _governorate_names()
    g, c = plain(governorate_col), plain(city_col)
    g_is = g in govs or g == 'grand tunis'
    c_is = c in govs or c == 'grand tunis'
    if g_is and not c_is:
        town = _town(city_col)
        # 'Grand Tunis' is a region, not a governorate: take it from the town
        gov = normalize_governorate(None, town) if g == 'grand tunis' and town else normalize_governorate(g, c)
        return gov, town, 'correct'
    if c_is and not g_is:
        town = _town(governorate_col)
        gov = normalize_governorate(None, town) if c == 'grand tunis' and town else normalize_governorate(c, g)
        return gov, town, 'swapped' if town else 'swapped_no_town'
    if g_is and c_is:
        if g == c or 'grand tunis' in (g, c):
            gov = normalize_governorate(c if g == 'grand tunis' else g)
            return gov, None, 'no_town'
        # e.g. 'Tunis' + 'Mahdia': the description says Mahdia; 'Tunis' is a default
        return normalize_governorate(c), None, 'conflict_city_column'
    town = _town(city_col) or _town(governorate_col)
    return normalize_governorate(governorate_col, city_col), town, 'neither'


@dataclass
class Dataset:
    train: pd.DataFrame
    test: pd.DataFrame
    priors: dict[str, dict]
    card: dict = field(default_factory=dict)

    def xy(self, split: str, property_type: str | None = None):
        df = self.train if split == 'train' else self.test
        if property_type:
            df = df[df['property_type'] == property_type]
        return df[FEATURES], np.log1p(df['price_tnd'].to_numpy()), df


DUPLICATE_KEY = ['property_type', 'price_tnd', 'surface_m2', 'city', 'latitude', 'longitude', 'rooms', 'bedrooms']
# After cleaning, 'rooms' is the serving-style derived value; the listed count is 'rooms_listed'.
_LISTED_KEY = [c if c != 'rooms' else 'rooms_listed' for c in DUPLICATE_KEY]


def clean(raw: pd.DataFrame, options: Options = V1) -> tuple[pd.DataFrame, dict]:
    card = {'input_rows': len(raw), 'removed': {}, 'changed': {}}

    def drop(mask, rule, df):
        card['removed'][rule] = int((~mask).sum())
        return df[mask]

    df = raw.copy()
    df = drop((df['transaction_type'] == 'sale') & df['property_type'].isin(TYPES), 'not_sale_or_other_type', df)
    df = df.assign(property_type=df['property_type'].map(TYPES))
    df = drop(df['price_tnd'].between(*PRICE_RANGE), 'price_out_of_range', df)
    lo = df['property_type'].map(lambda t: SURFACE_RANGE[t][0])
    hi = df['property_type'].map(lambda t: SURFACE_RANGE[t][1])
    df = drop(df['surface_m2'].between(lo, hi), 'surface_out_of_range', df)
    ppm = df['price_tnd'] / df['surface_m2']
    lo = df['property_type'].map(lambda t: PPM_RANGE[t][0])
    hi = df['property_type'].map(lambda t: PPM_RANGE[t][1])
    df = drop(ppm.between(lo, hi), 'price_per_m2_out_of_range', df)
    df = drop(~df.duplicated(subset=DUPLICATE_KEY), 'duplicate_listing', df)

    df = df.assign(
        transaction_type='sale',
        governorate_raw=df['governorate'], city_raw=df['city'],  # what the older models were trained on
        # governorate + city only: serving receives no free-text location
        governorate=[normalize_governorate(g, c) for g, c in zip(df['governorate'], df['city'])],
        city=df['city'].map(normalize_city),
        price_per_m2=df['price_tnd'] / df['surface_m2'],
    )
    for col in ('rooms', 'bedrooms', 'bathrooms'):
        df[col] = df[col].fillna(0).clip(0, 30)
    # Serving never receives a room count: the API takes bedrooms and the
    # request mapper derives rooms = bedrooms + 1 (land: + 0). Train on the
    # same derivation so the feature means the same thing at serving time.
    df['rooms_listed'] = df['rooms']
    df['rooms'] = df['bedrooms'] + (df['property_type'] != 'terrain').astype(int)

    if options.location == 'v2':
        derived = [derive_location(g, c) for g, c in zip(df['governorate_raw'], df['city_raw'])]
        df['governorate'] = [d[0] for d in derived]
        # no town given: the governorate name stands for "unspecified", as when a
        # user enters the governorate as the city
        df['city'] = [d[1] or d[0] for d in derived]
        df['location_pattern'] = [d[2] for d in derived]
        card['location_patterns'] = df['location_pattern'].value_counts().to_dict()
        card['changed']['town_taken_from_governorate_column'] = int(df['location_pattern'].eq('swapped').sum())
        card['changed']['governorate_from_city_column_on_conflict'] = int(
            df['location_pattern'].eq('conflict_city_column').sum())
    if options.drop_cross_town_duplicates:
        towns = df.groupby(['property_type', 'price_tnd', 'surface_m2'])['city'].transform('nunique')
        df = drop(towns <= 1, 'same_price_and_surface_in_several_towns', df)
    if options.drop_fractional_surfaces:
        df = drop(df['surface_m2'] % 1 == 0, 'surface_with_decimals', df)
    if options.coordinates in ('centroid_missing', 'none'):
        at_centroid = df['latitude'].eq(COUNTRY_CENTROID[0]) & df['longitude'].eq(COUNTRY_CENTROID[1])
        blank = at_centroid if options.coordinates == 'centroid_missing' else pd.Series(True, index=df.index)
        card['changed'][f'coordinates_blanked_{options.coordinates}'] = int(blank.sum())
        df.loc[blank, ['latitude', 'longitude']] = np.nan

    card['output_rows'] = len(df)
    card['by_type'] = df['property_type'].value_counts().to_dict()
    card['governorates'] = int(df['governorate'].nunique())
    card['unknown_governorate_rows'] = int((df['governorate'] == 'unknown').sum())
    return df.reset_index(drop=True), card


def split(df: pd.DataFrame, holdout_ids: frozenset | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if holdout_ids is not None:
        is_test = df['record_id'].isin(holdout_ids)
        return df[~is_test].copy(), df[is_test].copy()
    test_idx = []
    for _, part in df.groupby('property_type'):
        test_idx.extend(part.sample(frac=TEST_SHARE, random_state=SEED).index)
    is_test = df.index.isin(test_idx)
    return df[~is_test].copy(), df[is_test].copy()


def fit_priors(train: pd.DataFrame) -> dict[str, dict]:
    priors = {}
    for ptype, part in train.groupby('property_type'):
        cg = part.assign(k=part['city'] + '__' + part['governorate']).groupby('k')['price_per_m2'].agg(['median', 'size'])
        gv = part.groupby('governorate')['price_per_m2'].agg(['median', 'size'])
        priors[f'{ptype}__sale'] = {
            'city_governorate_price_m2': cg[cg['size'] >= PRIOR_MIN_COUNT]['median'].round(2).to_dict(),
            'governorate_price_m2': gv[gv['size'] >= PRIOR_MIN_COUNT]['median'].round(2).to_dict(),
            'global_price_m2': round(float(part['price_per_m2'].median()), 2),
        }
    return priors


def add_features(df: pd.DataFrame, priors: dict[str, dict]) -> pd.DataFrame:
    df = df.copy()
    df['city_governorate'] = df['city'] + '__' + df['governorate']
    local, gov = [], []
    for ptype, cg_key, g in zip(df['property_type'], df['city_governorate'], df['governorate']):
        p = priors.get(f'{ptype}__sale', {})
        g_prior = p.get('governorate_price_m2', {}).get(g)
        l_prior = p.get('city_governorate_price_m2', {}).get(cg_key) or g_prior or p.get('global_price_m2')
        local.append(l_prior)
        gov.append(g_prior or l_prior)
    df['local_avg_price_m2'] = local
    df['gov_avg_price_m2'] = gov
    df['size_x_local_price'] = df['surface_m2'] * df['local_avg_price_m2']
    return df


def build(csv_path: Path = LISTINGS_CSV, options: Options = V1) -> Dataset:
    raw = pd.read_csv(csv_path)
    df, card = clean(raw, options)
    train, test = split(df, options.holdout_ids)
    priors = fit_priors(train)
    train, test = add_features(train, priors), add_features(test, priors)
    card.update({
        'source': str(csv_path.name),
        'source_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        'train_rows': len(train), 'test_rows': len(test),
        'train_by_type': train['property_type'].value_counts().to_dict(),
        'test_by_type': test['property_type'].value_counts().to_dict(),
        'listings_in_both_splits': int(len(train.merge(test, on=_LISTED_KEY))),
        'location_normalization': LOCATION_NORMALIZATION,
        'options': {'location': options.location, 'drop_cross_town_duplicates': options.drop_cross_town_duplicates,
                    'drop_fractional_surfaces': options.drop_fractional_surfaces, 'coordinates': options.coordinates,
                    'holdout_ids': len(options.holdout_ids) if options.holdout_ids is not None else None},
        'rows_where_town_differs_from_governorate': int(
            (pd.concat([train, test])['city'] != pd.concat([train, test])['governorate']).sum()),
        'rules': {'price_range': PRICE_RANGE, 'surface_range': SURFACE_RANGE, 'ppm_range': PPM_RANGE,
                  'prior_min_count': PRIOR_MIN_COUNT, 'test_share': TEST_SHARE, 'seed': SEED},
    })
    return Dataset(train=train, test=test, priors=priors, card=card)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    ds = build()
    print(json.dumps(ds.card, indent=1, default=str))
