"""Score a registered valuation version against the current champions through
the serving code path (registry handle -> InferenceBundle.predict), on the
held-out listings used for the variant E comparison (README, "Valuation").

    python -m ml.valuation.evaluate_served --version estate_e_20260929 [--out report.json]

Two input styles, both without coordinates (the API never receives any):
  user_style  the corrected governorate and town, as a user picking them from
              the form would send. The promotion decision uses this one.
  raw         the listing's own governorate/city columns (swapped in most rows).

Promotion rule, fixed before the results were seen. A property type is
promoted only if, on user_style input:
  1. the version's median APE is lower than the champion's,
  2. the upper end of the 95% bootstrap interval of (version - champion)
     median APE is below +0.01 (not plausibly more than a point worse),
  3. its median predicted/actual is within [0.90, 1.10],
  4. every prediction succeeded.
Nothing is written; the report says which types pass.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('PRELOAD_LEGAL_EMBEDDING_MODEL', 'False')

TYPES = ('appartement', 'maison', 'terrain')
MAX_WORSE_CI = 0.01
BIAS_RANGE = (0.90, 1.10)


def _metrics(actual, pred) -> dict:
    ape = np.abs(pred - actual) / actual
    return {'n': int(len(actual)), 'median_ape': round(float(np.median(ape)), 3),
            'within_20pct': round(float(np.mean(ape <= 0.2)), 3),
            'median_pred_over_actual': round(float(np.median(pred / actual)), 3)}


def _served_predictions(handle, rows, style: str, ptype: str) -> tuple[np.ndarray, int]:
    from estatemind.intelligence.valuation.inference.request_mapper import map_request

    preds, failures = [], 0
    for _, r in rows.iterrows():
        gov, city = (r['governorate'], r['city']) if style == 'user_style' else (r['governorate_raw'], r['city_raw'])
        try:
            mapped = map_request({'property_type': 'apartment' if ptype == 'appartement' else ptype,
                                  'governorate': gov, 'city': city, 'size_m2': r['surface_m2'],
                                  'bedrooms': r['bedrooms'], 'bathrooms': r['bathrooms']})
            mapped['model_property_type'] = ptype
            value = float(handle.bundle.predict(mapped, {'avg_price_per_m2': None}).estimated_price)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(value)
        except Exception:
            failures += 1
            value = np.nan
        preds.append(value)
    return np.array(preds, dtype=float), failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()

    import django
    django.setup()
    from estatemind.intelligence.valuation.models import ValuationModelVersion
    from estatemind.intelligence.valuation.services.model_registry import ValuationModelRegistry, registry_key
    from ml.shared.listings_dataset import build
    from ml.valuation.compare_data_fixes import _bootstrap_diff
    from ml.valuation.train_catboost_bundle import variant_e_options

    eval_rows = build(options=variant_e_options()).test
    reg = ValuationModelRegistry()
    report = {'version': args.version, 'rule': {'max_worse_ci': MAX_WORSE_CI, 'bias_range': BIAS_RANGE},
              'by_type': {}, 'promote': []}
    for ptype in TYPES:
        candidate = ValuationModelVersion.objects.get(model_name=registry_key(ptype), version=args.version[-20:])
        cand_handle = reg.maybe_load_bundle(reg._version_to_handle(candidate))
        champ_handle, champion = reg.get_active_model(ptype)
        champ_handle = reg.maybe_load_bundle(champ_handle)
        rows = eval_rows[eval_rows['property_type'] == ptype]
        actual = rows['price_tnd'].to_numpy(dtype=float)

        entry = {'champion_version': getattr(champion, 'version', '?'), 'n': int(len(rows))}
        for style in ('user_style', 'raw'):
            cand, cand_fail = _served_predictions(cand_handle, rows, style, ptype)
            champ, champ_fail = _served_predictions(champ_handle, rows, style, ptype)
            ok = np.isfinite(cand) & np.isfinite(champ)
            entry[style] = {
                'candidate': {**_metrics(actual[ok], cand[ok]), 'failures': cand_fail},
                'champion': {**_metrics(actual[ok], champ[ok]), 'failures': champ_fail},
                'candidate_minus_champion': _bootstrap_diff(actual[ok], cand[ok], champ[ok]),
            }
        u = entry['user_style']
        checks = {
            'lower_median_ape': u['candidate']['median_ape'] < u['champion']['median_ape'],
            'not_plausibly_worse': u['candidate_minus_champion']['ci95'][1] < MAX_WORSE_CI,
            'unbiased': BIAS_RANGE[0] <= u['candidate']['median_pred_over_actual'] <= BIAS_RANGE[1],
            'no_failures': u['candidate']['failures'] == 0,
        }
        entry['checks'] = checks
        if all(checks.values()):
            report['promote'].append(ptype)
        report['by_type'][ptype] = entry
        print(ptype, json.dumps(entry), flush=True)

    text = json.dumps(report, indent=1, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
