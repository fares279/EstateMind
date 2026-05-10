"""
Simulation environment — property units and zone price index.

PropertyUnit is a lightweight dataclass representing a single
listing on the market.  Zone price indices are seeded from the
delegation CSV and evolve each simulation step.
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .config import DELEGATION_DATA

# Property types in scope
PROPERTY_TYPES = ["apartment", "house", "commercial", "land"]

# National average annual income (TND) — used for affordability
NATIONAL_ANNUAL_INCOME = 14_400.0   # TND


# ---------------------------------------------------------------------------
# Zone price index
# ---------------------------------------------------------------------------
def build_zone_price_index() -> dict:
    """
    Returns a dict keyed by (delegation, property_type) with:
        { "avg_price", "min_price", "max_price", "trend", "is_coastal",
          "governorate", "population" }

    Only apartment & house types have enough data coverage in the CSV;
    commercial & land fall back gracefully.
    """
    index: dict = {}
    for d in DELEGATION_DATA:
        for ptype in PROPERTY_TYPES:
            avg = d.get(f"{ptype}_avg", 0.0)
            mn  = d.get(f"{ptype}_min", 0.0)
            mx  = d.get(f"{ptype}_max", 0.0)
            trend = d.get(f"{ptype}_trend", 0.0)
            # Some CSV rows have zero values for commercial/land — use apartment as proxy
            if avg == 0.0:
                avg   = d.get("apartment_avg", 1500.0) * (0.85 if ptype == "house" else 1.1)
                mn    = avg * 0.6
                mx    = avg * 1.5
            index[(d["delegation"], ptype)] = {
                "avg_price":   avg,
                "min_price":   max(1.0, mn),
                "max_price":   mx,
                "trend":       trend,
                "is_coastal":  d.get("is_coastal", False),
                "governorate": d["governorate"],
                "population":  d["population"],
                "delegation":  d["delegation"],
            }
    return index


# Build once at import
ZONE_PRICE_INDEX: dict = build_zone_price_index()

# Ordered list of (delegation, ptype) zone keys
ZONE_KEYS = list(ZONE_PRICE_INDEX.keys())


def random_zone_key(property_type: Optional[str] = None) -> tuple:
    """Pick a random zone, optionally filtering by property type."""
    if property_type:
        keys = [(d, p) for (d, p) in ZONE_KEYS if p == property_type]
        if not keys:
            keys = ZONE_KEYS
    else:
        keys = ZONE_KEYS
    return random.choice(keys)


def zone_avg_price(zone_index: dict, delegation: str, ptype: str) -> float:
    """Safe lookup; returns national fallback if zone not found."""
    entry = zone_index.get((delegation, ptype))
    if entry:
        return float(entry["avg_price"])
    # Fallback: mean over matching property type
    vals = [v["avg_price"] for (d, p), v in zone_index.items() if p == ptype]
    return float(sum(vals) / len(vals)) if vals else 1500.0


# ---------------------------------------------------------------------------
# PropertyUnit dataclass
# ---------------------------------------------------------------------------
@dataclass
class PropertyUnit:
    """
    A single property listing active on the market.
    Prices are in TND/m².
    """
    unit_id:          str       = field(default_factory=lambda: str(uuid.uuid4())[:8])
    property_type:    str       = "apartment"
    delegation:       str       = ""
    governorate:      str       = ""
    is_coastal:       bool      = False
    area_m2:          float     = 80.0         # square metres
    ask_price_per_m2: float     = 2000.0       # TND / m²
    reservation_price_per_m2: float = 0.0      # minimum seller will accept
    months_on_market: int       = 0
    seller_id:        Optional[str] = None
    is_available:     bool      = True
    is_new_build:     bool      = False
    # Track transaction outcome
    sold_price_per_m2: Optional[float] = None
    buyer_id:         Optional[str] = None

    @property
    def total_ask_price(self) -> float:
        return self.ask_price_per_m2 * self.area_m2

    @property
    def total_sold_price(self) -> Optional[float]:
        if self.sold_price_per_m2 is None:
            return None
        return self.sold_price_per_m2 * self.area_m2


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------
def make_property_unit(
    zone_index: dict,
    delegation: str,
    ptype: str,
    is_new_build: bool = False,
    markup_pct: float = 0.0,
) -> PropertyUnit:
    """
    Create a PropertyUnit seeded from zone_index price with random variation.
    """
    entry = zone_index.get((delegation, ptype), {})
    avg   = entry.get("avg_price", 1500.0)
    mn    = entry.get("min_price", avg * 0.6)
    mx    = entry.get("max_price", avg * 1.4)
    gov   = entry.get("governorate", "")
    coastal = entry.get("is_coastal", False)

    # Random ask price within min-max range, with log-normal noise
    noise     = random.gauss(0.0, 0.08)
    ask       = avg * (1.0 + noise + markup_pct)
    ask       = max(mn, min(mx, ask))
    reservation = ask * random.uniform(0.82, 0.92)

    # Typical area by type
    area_range = {
        "apartment": (50, 160),
        "house":     (100, 350),
        "commercial":(40,  300),
        "land":      (200, 2000),
    }
    lo, hi = area_range.get(ptype, (60, 200))
    area = random.uniform(lo, hi)

    return PropertyUnit(
        property_type=ptype,
        delegation=delegation,
        governorate=gov,
        is_coastal=coastal,
        area_m2=round(area, 1),
        ask_price_per_m2=round(ask, 2),
        reservation_price_per_m2=round(reservation, 2),
        is_new_build=is_new_build,
    )
