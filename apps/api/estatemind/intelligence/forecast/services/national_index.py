"""The INS property price index (data/ins_property_price_index.csv) as the outlook's
growth rate and the measure of its error.

Statistiques Tunisie publishes a quarterly index (base 2015) of registered sale prices
for apartments, houses and residential land, 2000 Q1 onwards. A rolling-origin
backtest on it (every quarter from 2005 Q1, 1-4 quarters ahead) compared five ways to
set next year's growth: flat (0%, what most benchmark trends in delegations.csv
imply), the last 12 months, the 3- and 5-year average, and the average since 2000.
The average since 2000 had the lowest error for every type, so it is the outlook's
national growth; flat had the highest. The same backtest gives the error quantiles
used as interval half-widths. These are national figures: no regional series exists
at delegation level, so local accuracy is not measured.
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache

from config.paths import DATA_DIR

INDEX_CSV = DATA_DIR / 'ins_property_price_index.csv'
SERIES = {'apartment': 'apartment', 'house': 'house', 'land': 'land', 'commercial': 'built'}  # no commercial index
FIRST_ORIGIN = 20    # 2005 Q1: five years of history before the first backtest origin
METHODS = ('flat', 'last_12m', 'avg_3y', 'avg_5y', 'avg_all')
CHOSEN = 'avg_all'


@lru_cache(maxsize=1)
def _series() -> dict[str, list[tuple[int, int, float]]]:
    with open(INDEX_CSV, encoding='utf-8') as fh:
        rows = list(csv.DictReader(line for line in fh if not line.startswith('#')))
    return {col: [(int(r['year']), int(r['quarter']), float(r[col])) for r in rows]
            for col in ('apartment', 'house', 'land', 'built')}


def _log(col: str) -> list[float]:
    return [math.log(v) for *_, v in _series()[col]]


def _annual_rate(method: str, v: list[float], t: int) -> float:
    """Expected annual log growth from quarter t, by method."""
    if method == 'flat':
        return 0.0
    if method == 'last_12m':
        return v[t] - v[t - 4]
    if method == 'avg_3y':
        return (v[t] - v[t - 12]) / 3
    if method == 'avg_5y':
        return (v[t] - v[t - 20]) / 5
    return (v[t] - v[0]) / (t / 4)


def _quantile(values: list[float], q: float) -> float:
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


@lru_cache(maxsize=None)
def backtest(property_type: str) -> dict:
    """Mean absolute error (percentage points of growth) of each method, 4 quarters ahead,
    and the CHOSEN method's absolute-error quantiles for 1-4 quarters ahead."""
    col = SERIES.get(property_type, 'built')
    v = _log(col)
    mae = {}
    for m in METHODS:
        errs = [abs(math.expm1(v[t + 4] - v[t]) - math.expm1(_annual_rate(m, v, t))) for t in range(FIRST_ORIGIN, len(v) - 4)]
        mae[m] = round(100 * sum(errs) / len(errs), 2)
    quantiles = {}
    for k in (1, 2, 3, 4):
        errs = [abs(math.expm1(v[t + k] - v[t]) - math.expm1(_annual_rate(CHOSEN, v, t) * k / 4))
                for t in range(FIRST_ORIGIN, len(v) - k)]
        quantiles[k] = {'q80': _quantile(errs, 0.80), 'q90': _quantile(errs, 0.90), 'n': len(errs)}
    year, quarter, _ = _series()[col][-1]
    return {'series': col, 'mae_12m_pp': mae, 'chosen': CHOSEN, 'error_quantiles': quantiles,
            'origins': len(v) - 4 - FIRST_ORIGIN, 'last_quarter': f'{year} Q{quarter}'}


def expected_annual_growth_pct(property_type: str) -> float:
    """National growth for the next 12 months, % (CHOSEN method at the latest quarter)."""
    v = _log(SERIES.get(property_type, 'built'))
    return 100 * math.expm1(_annual_rate(CHOSEN, v, len(v) - 1))


def interval_halfwidth(property_type: str, months_ahead: float, coverage: float = 0.90) -> float:
    """Relative half-width of the interval `months_ahead` months out, from the backtest's
    absolute-error quantiles (linear between quarters, 0 at the origin; beyond 12 months
    it widens with the square root of time)."""
    if months_ahead <= 0:
        return 0.0
    key = 'q90' if coverage >= 0.85 else 'q80'
    q = {k: x[key] for k, x in backtest(property_type)['error_quantiles'].items()}
    k = months_ahead / 3
    if k >= 4:
        return q[4] * math.sqrt(k / 4)
    lo = int(k)
    lo_q = q[lo] if lo else 0.0
    return lo_q + (q[lo + 1] - lo_q) * (k - lo)
