"""Distance to the Tunisian coast, from a simplified coastline (data/tunisia_coastline.csv).

The coastline is a hand-placed polyline through ~80 coastal towns and headlands
(mainland, Djerba, Kerkennah), accurate to a few kilometres. A delegation is coastal
when its centre lies within COASTAL_KM of it. This replaces the governorate-wide
rule, which marked every delegation of a coastal governorate coastal (and Djerba not).
"""
from __future__ import annotations

import csv
import math
from functools import lru_cache

from config.paths import DATA_DIR

COASTLINE_CSV = DATA_DIR / 'tunisia_coastline.csv'
COASTAL_KM = 5.0
# Delegations with a coastline whose centre lies further inland than COASTAL_KM (islands,
# large coastal delegations). At 8 km, inland delegations of Greater Tunis bordering the
# Lake of Tunis or a sebkha were counted as coastal, so the threshold is 5 km plus this list.
KNOWN_COASTAL = {
    'djerba midoun', 'djerba houmt souk', 'djerba ajim', 'kerkennah', 'bizerte nord', 'sejnane',
    'ghar el melh', 'kalaat el andalous', 'skhira', 'sfax sud', 'gabes sud', 'mareth dkhila', 'ben gardane',
    'jebiniana',
}
_EARTH_KM = 6371.0


@lru_cache(maxsize=1)
def _segments() -> list[tuple[tuple[float, float], tuple[float, float]]]:
    lines: dict[str, list[tuple[float, float]]] = {}
    with open(COASTLINE_CSV, encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            lines.setdefault(row['segment'], []).append((float(row['lat']), float(row['lon'])))
    return [(a, b) for pts in lines.values() for a, b in zip(pts, pts[1:])]


def _to_xy(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    """Local equirectangular projection in km (fine at this scale)."""
    return (math.radians(lon) * _EARTH_KM * math.cos(math.radians(lat0)), math.radians(lat) * _EARTH_KM)


def distance_to_coast_km(lat: float, lon: float) -> float:
    px, py = _to_xy(lat, lon, lat)
    best = float('inf')
    for a, b in _segments():
        ax, ay = _to_xy(*a, lat)
        bx, by = _to_xy(*b, lat)
        dx, dy = bx - ax, by - ay
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


def is_coastal(lat: float | None, lon: float | None, name: str = '') -> bool | None:
    """Within COASTAL_KM of the coast, or a known coastal delegation. None without coordinates."""
    from estatemind.intelligence.valuation.inference.location import plain

    if plain(name) in KNOWN_COASTAL:
        return True
    if lat is None or lon is None:
        return None
    return distance_to_coast_km(lat, lon) <= COASTAL_KM
