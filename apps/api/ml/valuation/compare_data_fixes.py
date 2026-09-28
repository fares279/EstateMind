"""Compare valuation models trained with each data fix, on one held-out set.

    python -m ml.valuation.compare_data_fixes [--iterations N] [--out report.json]

Held-out set: the previous v2 test listings (so neither v2 nor any variant
trained on them) that survive the strictest cleaning. Every model is scored
twice: with coordinates (as in training) and without (as served: the
valuation API never receives coordinates). Nothing is written to artifacts or
the registry.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('PRELOAD_LEGAL_EMBEDDING_MODEL', 'False')

TYPES = ('appartement', 'maison', 'terrain')
PREVIOUS_V2 = 'estate_v2_20260927'
MIN_TOWN_ROWS = 8


def _metrics(actual, pred) -> dict:
    ape = np.abs(pred - actual) / actual
    return {'n': int(len(actual)), 'median_ape': round(float(np.median(ape)), 3),
            'within_20pct': round(float(np.mean(ape <= 0.2)), 3),
            'median_pred_over_actual': round(float(np.median(pred / actual)), 3)}


def _variants(holdout):
    from ml.shared.listings_dataset import Options
    base = dict(holdout_ids=holdout)
    return {
        'A_location_fix': Options(location='v2', **base),
        'B_+cross_town_duplicates': Options(location='v2', drop_cross_town_duplicates=True, **base),
        'C_+fractional_surfaces': Options(location='v2', drop_cross_town_duplicates=True,
                                          drop_fractional_surfaces=True, **base),
        'D_+centroid_coords_missing': Options(location='v2', drop_cross_town_duplicates=True,
                                              drop_fractional_surfaces=True, coordinates='centroid_missing', **base),
        'E_+no_coordinates': Options(location='v2', drop_cross_town_duplicates=True,
                                     drop_fractional_surfaces=True, coordinates='none', **base),
    }


def _bootstrap_diff(actual, pred_a, pred_b, draws=2000, seed=0) -> dict:
    """Median APE of a minus b, with a 95% bootstrap interval over listings.
    Negative = a is more accurate."""
    rng = np.random.default_rng(seed)
    ape_a, ape_b = np.abs(pred_a - actual) / actual, np.abs(pred_b - actual) / actual
    idx = rng.integers(0, len(actual), size=(draws, len(actual)))
    diffs = np.median(ape_a[idx], axis=1) - np.median(ape_b[idx], axis=1)
    return {'diff': round(float(np.median(ape_a) - np.median(ape_b)), 3),
            'ci95': [round(float(np.percentile(diffs, 2.5)), 3), round(float(np.percentile(diffs, 97.5)), 3)]}


def _predict(model, X: pd.DataFrame, served: bool) -> np.ndarray:
    X = X.copy()
    if served:
        X[['latitude', 'longitude']] = np.nan
    return np.expm1(model.predict(X))


def _importance(model) -> dict:
    names = list(model.feature_names_)
    values = model.get_feature_importance()
    keep = ('city', 'city_governorate', 'governorate', 'local_avg_price_m2', 'latitude', 'longitude', 'surface_m2')
    return {n: round(float(v), 1) for n, v in zip(names, values) if n in keep}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iterations', type=int, default=2000)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()

    import django
    django.setup()
    from config.paths import ARTIFACTS_DIR
    from ml.shared.listings_dataset import FEATURES, V1, build
    from ml.valuation.train_catboost_bundle import champion_predictions, train_model

    v1 = build(options=V1)
    holdout = frozenset(v1.test['record_id'])
    variants = {name: build(options=opt) for name, opt in _variants(holdout).items()}
    strict = variants['C_+fractional_surfaces'].test
    eval_ids = set(strict['record_id'])

    report = {'held_out': {'previous_v2_test_rows': len(holdout), 'surviving_all_cleaning': len(eval_ids)},
              'data_cards': {n: {k: d.card.get(k) for k in ('output_rows', 'removed', 'changed', 'location_patterns',
                                                            'rows_where_town_differs_from_governorate')}
                             for n, d in variants.items()},
              'by_type': {}}

    v1_eval = v1.test[v1.test['record_id'].isin(eval_ids)]
    champions = {cond: champion_predictions(v1_eval if cond == 'with_coords'
                                            else v1_eval.assign(latitude=np.nan, longitude=np.nan))
                 for cond in ('with_coords', 'served_no_coords')}

    for ptype in TYPES:
        rows = {}
        ref = strict[strict['property_type'] == ptype].set_index('record_id')
        order = list(ref.index)
        actual = ref['price_tnd'].to_numpy()
        towns = ref['city'].to_numpy()
        town_known = (ref['city'] != ref['governorate']).to_numpy()

        served_preds = {}

        def score(pred, name, importance=None):
            served_preds[name] = pred['served_no_coords']
            entry = {}
            for cond, p in pred.items():
                entry[cond] = _metrics(actual, p)
                entry[cond + '_town_known_rows'] = _metrics(actual[town_known], p[town_known])
            served = pred['served_no_coords']
            per_town = {}
            for t in pd.unique(towns):
                mask = towns == t
                if mask.sum() >= MIN_TOWN_ROWS:
                    per_town[t] = round(float(np.median(np.abs(served[mask] - actual[mask]) / actual[mask])), 3)
            entry['served_median_ape_per_town'] = per_town
            if importance:
                entry['feature_importance'] = importance
            rows[name] = entry

        # current champions (raw location values, as they were trained)
        part = v1_eval[v1_eval['property_type'] == ptype].set_index('record_id').loc[order]
        pos = {rid: i for i, rid in enumerate(v1_eval[v1_eval['property_type'] == ptype]['record_id'])}
        idx = [pos[r] for r in order]
        score({cond: champions[cond][ptype][0][idx] for cond in champions}, 'champion')

        # previous v2, on its own (v1) features
        v2_model = joblib.load(ARTIFACTS_DIR / 'valuation' / 'models' / PREVIOUS_V2 / f'bytype__{ptype}__catboost.joblib')
        Xv2 = part[FEATURES]
        score({'with_coords': _predict(v2_model, Xv2, False), 'served_no_coords': _predict(v2_model, Xv2, True)},
              'previous_v2', _importance(v2_model))

        for name, ds in variants.items():
            X, y, _ = ds.xy('train', ptype)
            model = train_model(X, y, args.iterations, seed=42)
            Xt = ds.test.set_index('record_id').loc[order][FEATURES]
            score({'with_coords': _predict(model, Xt, False), 'served_no_coords': _predict(model, Xt, True)},
                  name, _importance(model))
            print(ptype, name, json.dumps(rows[name]['served_no_coords']), flush=True)
        rows['served_differences_with_ci'] = {
            f'{a} vs {b}': _bootstrap_diff(actual, served_preds[a], served_preds[b])
            for a in variants for b in ('champion', 'previous_v2')
        }
        report['by_type'][ptype] = rows

    text = json.dumps(report, indent=1, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
