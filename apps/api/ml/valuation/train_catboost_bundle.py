"""Train the CatBoost valuation models that serving uses, and compare them
with the current champions on the same held-out listings.

    python -m ml.valuation.train_catboost_bundle [--register] [--iterations N]

Writes artifacts/valuation/models/<version>/:
    bytype__<appartement|maison|terrain>__catboost.joblib, global__catboost.joblib
    priors.json   (price priors, location normalization, data card, metrics)
With --register, adds each model to the registry as a challenger with 0%
traffic: nothing is served until someone promotes it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_ROOT))

TYPES = ('appartement', 'maison', 'terrain')


def metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    ape = np.abs(pred - actual) / actual
    ss_res = float(np.sum((actual - pred) ** 2))
    ss_tot = float(np.sum((actual - actual.mean()) ** 2))
    return {
        'n': int(len(actual)),
        'rmse_tnd': round(float(np.sqrt(np.mean((pred - actual) ** 2))), 0),
        'r2': round(1 - ss_res / ss_tot, 3) if ss_tot else None,
        'mape': round(float(ape.mean()), 3),
        'median_ape': round(float(np.median(ape)), 3),
        'within_20pct': round(float(np.mean(ape <= 0.2)), 3),
        'median_pred_over_actual': round(float(np.median(pred / actual)), 3),
    }


def train_model(X: pd.DataFrame, y: np.ndarray, iterations: int, seed: int):
    from catboost import CatBoostRegressor

    from ml.shared.listings_dataset import CATEGORICAL
    rng = np.random.default_rng(seed)
    val = rng.random(len(X)) < 0.15
    model = CatBoostRegressor(iterations=iterations, learning_rate=0.05, depth=6, loss_function='RMSE',
                              random_seed=seed, verbose=False, allow_writing_files=False)
    model.fit(X[~val], y[~val], cat_features=CATEGORICAL, eval_set=(X[val], y[val]),
              early_stopping_rounds=100, use_best_model=True)
    return model


def champion_predictions(test: pd.DataFrame) -> dict[str, np.ndarray]:
    """Current champions, on the pure model path (no sentiment/image multipliers),
    fed the raw location values they were trained on."""
    import django
    django.setup()
    from estatemind.intelligence.valuation.inference.request_mapper import map_request
    from estatemind.intelligence.valuation.services.model_registry import ValuationModelRegistry

    reg = ValuationModelRegistry()
    out = {}
    for ptype in TYPES:
        part = test[test['property_type'] == ptype]
        handle, version = reg.get_active_model(ptype)
        handle = reg.maybe_load_bundle(handle)
        preds = []
        for _, r in part.iterrows():
            mapped = map_request({'property_type': ptype if ptype != 'appartement' else 'apartment',
                                  'governorate': r['governorate_raw'], 'city': r['city_raw'],
                                  'size_m2': r['surface_m2'], 'rooms': r['rooms'], 'bedrooms': r['bedrooms'],
                                  'bathrooms': r['bathrooms'], 'latitude': r['latitude'],
                                  'longitude': r['longitude']})
            mapped['model_property_type'] = ptype
            preds.append(handle.bundle.predict(mapped, {'avg_price_per_m2': None}).estimated_price)
        out[ptype] = (np.array(preds, dtype=float), getattr(version, 'version', '?'))
    return out


def variant_e_options():
    """Variant E, holding out the previous v2 test listings (see compare_data_fixes)."""
    from ml.shared.listings_dataset import V1, Options, build
    holdout = frozenset(build(options=V1).test['record_id'])
    return Options(location='v2', drop_cross_town_duplicates=True, drop_fractional_surfaces=True,
                   coordinates='none', holdout_ids=holdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iterations', type=int, default=2000)
    parser.add_argument('--register', action='store_true')
    parser.add_argument('--version', default=f'estate_v2_{date.today():%Y%m%d}')
    parser.add_argument('--options', choices=('v2', 'e'), default='v2',
                        help="'v2': the default cleaning. 'e': variant E from docs/ml/valuation-training-data.md "
                             "(per-row location fix, generated-looking rows dropped, no coordinates), with the "
                             "previous v2 test listings held out so evaluate_served compares on unseen rows.")
    args = parser.parse_args()

    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    os.environ.setdefault('PRELOAD_LEGAL_EMBEDDING_MODEL', 'False')
    from config.paths import ARTIFACTS_DIR
    from ml.shared.listings_dataset import FEATURES, build

    ds = build(options=variant_e_options()) if args.options == 'e' else build()
    out_dir = ARTIFACTS_DIR / 'valuation' / 'models' / args.version
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {'version': args.version, 'data_card': ds.card, 'models': {}}
    champions = champion_predictions(ds.test)
    for ptype in (*TYPES, 'global'):
        X, y, _ = ds.xy('train', None if ptype == 'global' else ptype)
        model = train_model(X, y, args.iterations, seed=42)
        name = 'global__catboost.joblib' if ptype == 'global' else f'bytype__{ptype}__catboost.joblib'
        joblib.dump(model, out_dir / name)
        entry = {'artifact': name, 'best_iteration': int(model.get_best_iteration() or 0)}
        if ptype == 'global':
            Xt, yt, _ = ds.xy('test')
            entry['test'] = metrics(np.expm1(yt), np.expm1(model.predict(Xt)))
        else:
            Xt, yt, part = ds.xy('test', ptype)
            actual = np.expm1(yt)
            entry['test'] = metrics(actual, np.expm1(model.predict(Xt[FEATURES])))
            old_pred, old_version = champions[ptype]
            entry['champion_on_same_test'] = {'version': old_version, **metrics(actual, old_pred)}
        report['models'][ptype] = entry
        print(ptype, json.dumps(entry), flush=True)

    (out_dir / 'priors.json').write_text(json.dumps({
        'location_normalization': ds.card['location_normalization'],
        'priors': ds.priors, 'report': report,
    }, indent=1, default=str), encoding='utf-8')

    if args.register:
        from config.paths import to_artifact_ref
        from estatemind.intelligence.valuation.services.model_registry import ValuationModelRegistry, registry_key
        reg = ValuationModelRegistry()
        for ptype, entry in report['models'].items():
            t = entry['test']
            reg.register_challenger(
                artifact_path=to_artifact_ref(out_dir / entry['artifact']), model_name=registry_key(ptype),
                version=args.version[-20:], training_date=date.today(),
                training_data_hash=ds.card['source_sha256'], training_samples=ds.card['train_rows'],
                eval_rmse=t['rmse_tnd'], eval_r2=t['r2'] or 0, eval_mape=t['mape'], eval_holdout_size=t['n'],
                status='challenger', ab_traffic_pct=0,
                notes=f"ml.valuation.train_catboost_bundle; test median APE {t['median_ape']}, "
                      f"within 20% {t['within_20pct']}; not promoted (pending review)",
            )
        print('registered as 0%-traffic challengers')
    print(f'artifacts: {out_dir}')


if __name__ == '__main__':
    main()
