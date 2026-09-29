"""Sanity checks for deal-scanner and portfolio inputs.

Absurd inputs are rejected with a plain message instead of being scored into
precise-looking nonsense (5,000,000,000 TND for 20 m2 once scored 44/100
'Fair'). Unusual but possible ones are accepted with a warning. Delegations are
matched to their governorate case- and accent-insensitively.
"""
from __future__ import annotations

from estatemind.intelligence.valuation.inference.location import plain

PRICE_LIMITS = (1_000, 200_000_000)  # TND
SURFACE_LIMITS = {'apartment': (10, 2_000), 'house': (20, 10_000), 'land': (20, 5_000_000),
                  'commercial': (5, 50_000)}
BENCHMARK_PREFIX = {'apartment': 'apt', 'house': 'house', 'land': 'land', 'commercial': 'comm'}
TYPE_WORDS = {'apartment': 'apartments', 'house': 'houses', 'land': 'land', 'commercial': 'commercial property'}
REJECT_FACTOR = 10   # price/m2 more than 10x the area's benchmark maximum (or under a tenth of its minimum)
WARN_FACTOR = 2


class InvalidListing(ValueError):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


def resolve_delegation(governorate: str, delegation: str):
    """The Delegation named `delegation` in `governorate` (case/accent-insensitive).
    Returns (delegation or None, canonical governorate name or None)."""
    from estatemind.market.core.models import Delegation, Region
    gov_key = plain(governorate)
    region = next((r for r in Region.objects.all() if plain(r.governorate) == gov_key), None)
    if not delegation:
        return None, region.governorate if region else None
    del_key = plain(delegation)
    for d in Delegation.objects.select_related('region'):
        if plain(d.name) == del_key and (region is None or d.region_id == region.id):
            return d, d.region.governorate
    return None, region.governorate if region else None


def check_delegation(governorate: str, delegation: str):
    """Raise InvalidListing unless the delegation exists in that governorate."""
    from estatemind.market.core.models import Delegation
    if not delegation:
        return None
    match, gov_name = resolve_delegation(governorate, delegation)
    if match:
        return match
    elsewhere = [d for d in Delegation.objects.select_related('region') if plain(d.name) == plain(delegation)]
    if elsewhere:
        raise InvalidListing(f"{elsewhere[0].name} is in {elsewhere[0].region.governorate}, not "
                             f"{gov_name or governorate}. Choose an area in the selected governorate.", 'delegation')
    raise InvalidListing(f"'{delegation}' is not a delegation of {gov_name or governorate}. "
                         "Choose one from the list.", 'delegation')


def check_listing(price, surface, property_type: str, governorate: str, delegation: str = '') -> list[str]:
    """Validate a listing. Raises InvalidListing for implausible inputs; returns
    warnings (plain sentences) for unusual ones."""
    try:
        price, surface = float(price), float(surface)
    except (TypeError, ValueError):
        raise InvalidListing('Price and surface must be numbers.')
    ptype = property_type if property_type in SURFACE_LIMITS else 'apartment'
    if not PRICE_LIMITS[0] <= price <= PRICE_LIMITS[1]:
        raise InvalidListing(f"A price of {price:,.0f} TND is outside the range we can analyse "
                             f"({PRICE_LIMITS[0]:,}–{PRICE_LIMITS[1]:,} TND). Please check the figure.", 'listing_price_tnd')
    lo, hi = SURFACE_LIMITS[ptype]
    if not lo <= surface <= hi:
        raise InvalidListing(f"A surface of {surface:,.0f} m² is not plausible for {TYPE_WORDS[ptype]} "
                             f"({lo:,}–{hi:,} m²). Please check the figure.", 'surface_m2')
    deleg = check_delegation(governorate, delegation)

    ppm = price / surface
    band = _benchmark_band(deleg, governorate, ptype)
    if band is None:
        return []
    bmin, bmax, where = band
    place = f"{TYPE_WORDS[ptype]} in {where}"
    if ppm > bmax * REJECT_FACTOR or ppm < bmin / REJECT_FACTOR:
        raise InvalidListing(
            f"{ppm:,.0f} TND/m² is far outside the usual range for {place} ({bmin:,.0f}–{bmax:,.0f} TND/m²). "
            "Please check the price and the surface.", 'listing_price_tnd')
    if ppm > bmax * WARN_FACTOR or ppm < bmin / WARN_FACTOR:
        return [f"{ppm:,.0f} TND/m² is unusual for {place} (typically {bmin:,.0f}–{bmax:,.0f} TND/m²); "
                "treat this analysis with caution."]
    return []


def _benchmark_band(deleg, governorate: str, ptype: str):
    from estatemind.market.core.models import Delegation
    prefix = BENCHMARK_PREFIX[ptype]
    if deleg is not None:
        lo, hi = getattr(deleg, f'{prefix}_min_tnd'), getattr(deleg, f'{prefix}_max_tnd')
        if lo and hi:
            return float(lo), float(hi), deleg.name
    rows = [d for d in Delegation.objects.select_related('region') if plain(d.region.governorate) == plain(governorate)]
    los = [getattr(d, f'{prefix}_min_tnd') for d in rows if getattr(d, f'{prefix}_min_tnd')]
    his = [getattr(d, f'{prefix}_max_tnd') for d in rows if getattr(d, f'{prefix}_max_tnd')]
    if los and his:
        return float(min(los)), float(max(his)), rows[0].region.governorate
    return None
