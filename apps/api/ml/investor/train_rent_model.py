"""Train the monthly rent per m² model used for rental yields.

    python -m ml.investor.train_rent_model

Data: real rental listings in the database (not synthetic, price and area both
measured, 1-100 TND/m²/month). The model (CatBoost on log rent per m²: type,
delegation, governorate, surface, rooms, bedrooms, bathrooms) is compared with the
method it replaces, the median rent per m² of the delegation (>= 3 listings), else of
the governorate, else of the country, over 5 random 80/20 splits. It is written to
ARTIFACTS_DIR/investor/ only when its median APE is lower in every split, both with
and without the room counts (callers often know only the surface);
otherwise only the report is written (any earlier model is removed) and serving keeps
the medians.

Result on 2026-10-01 (572 listings): mean median APE 26.7% (surface only 26.9%) against
32.3% for the medians, but one split of five lost (32.3% vs 29.6%), so it is not adopted.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_ROOT))

FEATURES = ['property_type', 'delegation', 'governorate', 'area_sqm', 'rooms', 'bedrooms', 'bathrooms']
CATEGORICAL = ['property_type', 'delegation', 'governorate']
COUNTS = ['rooms', 'bedrooms', 'bathrooms']
PPM_RANGE = (1.0, 100.0)
SPLITS = 5


def load_rent_listings() -> pd.DataFrame:
    from estatemind.market.core.models import SYNTHETIC_SOURCE, Property

    rows = (Property.objects.filter(transaction_type='rent', property_type__in=('apartment', 'house'), price__gt=0,
                                    area_sqm__gt=0, price_imputed=False, area_imputed=False,
                                    delegation__isnull=False)
            .exclude(source=SYNTHETIC_SOURCE)
            .values('property_type', 'price', 'area_sqm', 'rooms', 'bedrooms', 'bathrooms',
                    'delegation__name', 'delegation__region__governorate'))
    df = pd.DataFrame(list(rows)).rename(columns={'delegation__name': 'delegation',
                                                  'delegation__region__governorate': 'governorate'})
    df['ppm'] = df['price'].astype(float) / df['area_sqm'].astype(float)
    return df[df['ppm'].between(*PPM_RANGE)].reset_index(drop=True)


def frame(df: pd.DataFrame) -> pd.DataFrame:
    """Model input. Place names are compared in plain form (location.plain), so user-typed
    names match the database names the model was trained on."""
    from estatemind.intelligence.valuation.inference.location import plain

    X = df.reindex(columns=FEATURES).copy()
    for c in CATEGORICAL:
        X[c] = X[c].fillna('').astype(str)
    for c in ('delegation', 'governorate'):
        X[c] = X[c].map(plain)
    for c in set(FEATURES) - set(CATEGORICAL):
        X[c] = pd.to_numeric(X[c], errors='coerce').fillna(-1).astype(float)
    return X


def without_counts(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(**{c: None for c in COUNTS})


def fit(df: pd.DataFrame, seed: int = 42):
    """Each listing is seen twice, with and without its room counts, so a request that
    gives only the surface (the scanner often does) is not read as "0 rooms"."""
    from catboost import CatBoostRegressor

    both = pd.concat([df, without_counts(df)], ignore_index=True)
    model = CatBoostRegressor(iterations=800, depth=5, learning_rate=0.05, loss_function='RMSE',
                              random_seed=seed, verbose=False, allow_writing_files=False)
    model.fit(frame(both), np.log(both['ppm']), cat_features=CATEGORICAL)
    return model


def median_baseline(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    by_del = train.groupby(['delegation', 'property_type'])['ppm'].agg(['median', 'count'])
    by_del = by_del[by_del['count'] >= 3]['median']
    by_gov = train.groupby(['governorate', 'property_type'])['ppm'].median()
    by_type = train.groupby('property_type')['ppm'].median()
    out = []
    for r in test.itertuples():
        for key, table in (((r.delegation, r.property_type), by_del), ((r.governorate, r.property_type), by_gov),
                           (r.property_type, by_type)):
            if key in table.index:
                out.append(table[key])
                break
        else:
            out.append(train['ppm'].median())
    return np.array(out, dtype=float)


def median_ape(pred: np.ndarray, actual: np.ndarray) -> float:
    return float(np.median(np.abs(pred - actual) / actual))


def evaluate(df: pd.DataFrame) -> list[dict]:
    rng = np.random.default_rng(0)
    folds = []
    for _ in range(SPLITS):
        test = rng.random(len(df)) < 0.2
        train, held = df[~test], df[test]
        actual = held['ppm'].to_numpy()
        model = fit(train)
        folds.append({'n_test': int(test.sum()),
                      'model_median_ape': round(median_ape(np.exp(model.predict(frame(held))), actual), 3),
                      'model_surface_only_median_ape': round(median_ape(
                          np.exp(model.predict(frame(without_counts(held)))), actual), 3),
                      'medians_median_ape': round(median_ape(median_baseline(train, held), actual), 3)})
    return folds


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    os.environ.setdefault('PRELOAD_LEGAL_EMBEDDING_MODEL', 'False')
    import django
    django.setup()
    import joblib

    from estatemind.intelligence.investor.services.rent_model import MODEL_PATH, REPORT_PATH

    df = load_rent_listings()
    folds = evaluate(df)
    wins = all(max(f['model_median_ape'], f['model_surface_only_median_ape']) < f['medians_median_ape']
               for f in folds)
    report = {
        'trained': date.today().isoformat(), 'listings': len(df),
        'by_type': df['property_type'].value_counts().to_dict(), 'features': FEATURES,
        'folds': folds,
        'model_median_ape': round(float(np.mean([f['model_median_ape'] for f in folds])), 3),
        'model_surface_only_median_ape': round(float(np.mean([f['model_surface_only_median_ape'] for f in folds])), 3),
        'medians_median_ape': round(float(np.mean([f['medians_median_ape'] for f in folds])), 3),
        'adopted': wins,
    }
    print(json.dumps(report, indent=1))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=1), encoding='utf-8')
    if not wins:
        # a model from an earlier run must not keep being served
        MODEL_PATH.unlink(missing_ok=True)
        print('The model does not beat the medians in every split; no model written, serving uses the medians.')
        return
    joblib.dump(fit(df), MODEL_PATH)
    print(f'written: {MODEL_PATH}')


if __name__ == '__main__':
    main()
