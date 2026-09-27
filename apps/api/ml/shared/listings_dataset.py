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


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    card = {'input_rows': len(raw), 'removed': {}}

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
    card['output_rows'] = len(df)
    card['by_type'] = df['property_type'].value_counts().to_dict()
    card['governorates'] = int(df['governorate'].nunique())
    card['unknown_governorate_rows'] = int((df['governorate'] == 'unknown').sum())
    return df.reset_index(drop=True), card


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
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


def build(csv_path: Path = LISTINGS_CSV) -> Dataset:
    raw = pd.read_csv(csv_path)
    df, card = clean(raw)
    train, test = split(df)
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
        'rules': {'price_range': PRICE_RANGE, 'surface_range': SURFACE_RANGE, 'ppm_range': PPM_RANGE,
                  'prior_min_count': PRIOR_MIN_COUNT, 'test_share': TEST_SHARE, 'seed': SEED},
    })
    return Dataset(train=train, test=test, priors=priors, card=card)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    ds = build()
    print(json.dumps(ds.card, indent=1, default=str))
