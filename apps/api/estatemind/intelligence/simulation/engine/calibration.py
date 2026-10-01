"""Calibrate the simulator's starting price levels to real listings.

The zone price index starts from the benchmark ranges in data/delegations.csv. This
module compares them with the median asking price per m² of real sale listings (not
synthetic, price and area both measured) and writes data/simulator_calibration.json:

  * a delegation and type with at least MIN_LISTINGS listings starts from its median;
  * any other zone keeps its benchmark, multiplied by the median listing/benchmark ratio
    of its governorate (for that type), or of the whole country when the governorate has
    fewer than MIN_ZONES calibrated delegations, but only for a type where that correction
    beats the raw benchmark in the leave-one-out check below (it does not for land).

The report measures how far the benchmarks are from the listings (before) and, by
leave-one-out over the delegations with data, how far the ratio-corrected benchmarks are
(after): the error expected in the zones without enough listings. It calibrates price
levels only. Agent behaviour (reward weights) is not calibrated: that needs observed
transactions, and the data has asking prices only.

    python manage.py calibrate_simulator
"""
from __future__ import annotations

import json
from datetime import date
from statistics import median

from config.paths import DATA_DIR

CALIBRATION_PATH = DATA_DIR / 'simulator_calibration.json'
MIN_LISTINGS = 5
MIN_ZONES = 3
CALIBRATED_TYPES = ('apartment', 'house', 'land')  # commercial: no listings


def real_sale_medians() -> dict[tuple[str, str, str], tuple[float, int]]:
    """{(delegation, governorate, type): (median price per m², count)} for real sale listings."""
    from estatemind.market.core.models import SYNTHETIC_SOURCE, Property

    groups: dict = {}
    rows = (Property.objects.filter(transaction_type='sale', property_type__in=CALIBRATED_TYPES,
                                    delegation__isnull=False, price__gt=0, area_sqm__gt=0,
                                    price_imputed=False, area_imputed=False)
            .exclude(source=SYNTHETIC_SOURCE)
            .values_list('delegation__name', 'delegation__region__governorate', 'property_type',
                         'price', 'area_sqm'))
    for name, gov, ptype, price, area in rows:
        groups.setdefault((name, gov, ptype), []).append(float(price) / float(area))
    return {k: (median(v), len(v)) for k, v in groups.items() if len(v) >= MIN_LISTINGS}


def _ape(predicted: float, actual: float) -> float:
    return abs(predicted - actual) / actual


def _ratio(ratios: list[tuple[str, float]], governorate: str, exclude: str | None = None) -> tuple[float, str]:
    local = [r for d, r in ratios if d != exclude and d.split('|')[1] == governorate]
    if len(local) >= MIN_ZONES:
        return median(local), 'governorate'
    rest = [r for d, r in ratios if d != exclude]
    return (median(rest), 'national') if rest else (1.0, 'none')


def build_calibration(index: dict, medians: dict) -> dict:
    """Calibration (zone multipliers and report) from the benchmark zone index and the listing medians."""
    by_name = {(d, p): (gov, m, n) for (d, gov, p), (m, n) in medians.items()}
    zones, report = {}, {}
    for ptype in CALIBRATED_TYPES:
        pairs = []  # ('delegation|governorate', benchmark, listings median)
        for (deleg, p), entry in index.items():
            if p == ptype and (deleg, p) in by_name and entry['avg_price'] > 0:
                pairs.append((f"{deleg}|{entry['governorate']}", entry['avg_price'], by_name[(deleg, p)][1]))
        ratios = [(k, m / b) for k, b, m in pairs]

        before = [_ape(b, m) for _, b, m in pairs]
        after = [_ape(b * _ratio(ratios, k.split('|')[1], exclude=k)[0], m) for k, b, m in pairs]
        # the correction is used only when it beats the raw benchmark out of sample
        correct = bool(after) and median(after) < median(before)
        report[ptype] = {
            'delegations_with_listings': len(pairs),
            'listings': sum(by_name[(k.split('|')[0], ptype)][2] for k, _, _ in pairs),
            'median_listing_to_benchmark': round(median(r for _, r in ratios), 3) if ratios else None,
            'benchmark_median_ape': round(median(before), 3) if before else None,
            'corrected_median_ape_leave_one_out': round(median(after), 3) if after else None,
            'zones_without_listings': 'ratio-corrected benchmark' if correct else 'benchmark (correction did not help)',
        }

        for (deleg, p), entry in index.items():
            if p != ptype or entry['avg_price'] <= 0:
                continue
            found = by_name.get((deleg, p))
            if found:
                zones[f'{deleg}|{p}'] = {'multiplier': round(found[1] / entry['avg_price'], 4),
                                         'basis': 'listings', 'listings': found[2]}
            elif correct:
                mult, basis = _ratio(ratios, entry['governorate'])
                zones[f'{deleg}|{p}'] = {'multiplier': round(mult, 4), 'basis': f'{basis}_ratio', 'listings': 0}
            else:
                zones[f'{deleg}|{p}'] = {'multiplier': 1.0, 'basis': 'benchmark', 'listings': 0}

    return {
        'generated': date.today().isoformat(),
        'method': ('Median asking price per m2 of real sale listings where a delegation has at least '
                   f'{MIN_LISTINGS}; elsewhere the benchmark times the median listing/benchmark ratio of '
                   f'its governorate (at least {MIN_ZONES} delegations) or of the country, for types where '
                   'that beats the raw benchmark out of sample.'),
        'scope': 'Starting price levels only; agent behaviour is not calibrated (no transaction data).',
        'report': report,
        'zones': zones,
    }


def calibrate_and_save() -> dict:
    from .environment import build_zone_price_index

    calibration = build_calibration(build_zone_price_index(calibrated=False), real_sale_medians())
    CALIBRATION_PATH.write_text(json.dumps(calibration, indent=1, ensure_ascii=False), encoding='utf-8')
    return calibration


def load_multipliers() -> dict[tuple[str, str], float]:
    """{(delegation, type): multiplier} from the saved calibration, or {} when there is none."""
    try:
        zones = json.loads(CALIBRATION_PATH.read_text(encoding='utf-8'))['zones']
    except (OSError, ValueError, KeyError):
        return {}
    return {tuple(k.rsplit('|', 1)): v['multiplier'] for k, v in zones.items()}
