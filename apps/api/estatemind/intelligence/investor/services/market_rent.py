"""Monthly rent per m2 from market data (real rental listings in the delegation
snapshots), so yields are rent / price rather than an assumed percentage."""
from __future__ import annotations

from statistics import median

from estatemind.intelligence.valuation.inference.location import plain

_TYPES = {'apartment': 'apartment', 'appartement': 'apartment', 'house': 'house', 'maison': 'house',
          'villa': 'house', 'land': 'land', 'terrain': 'land', 'commercial': 'commercial'}


def _latest_rent_segments(delegations, ptype: str):
    from estatemind.market.core.models import DelegationMarketSegment
    values = []
    for d in delegations:
        snap = d.market_snapshots.order_by('-as_of_date').first()
        if snap is None:
            continue
        segs = {s.property_type: s for s in DelegationMarketSegment.objects.filter(snapshot=snap, transaction_type='rent')}
        seg = segs.get(ptype) or segs.get('all')
        if seg and seg.median_price_per_sqm and seg.listing_count:
            values.append(float(seg.median_price_per_sqm))
    return values


def market_rent_per_m2(delegation: str, governorate: str, property_type: str) -> tuple[float | None, str]:
    """(monthly rent per m2, basis). basis: 'delegation', 'governorate' or 'none'."""
    from estatemind.market.core.models import Delegation
    ptype = _TYPES.get(str(property_type or '').lower(), 'apartment')
    if ptype == 'land':
        return None, 'none'  # land is not rented out
    gov_key, del_key = plain(governorate), plain(delegation)
    in_gov = [d for d in Delegation.objects.select_related('region') if plain(d.region.governorate) == gov_key]
    own = [d for d in in_gov if plain(d.name) == del_key]
    values = _latest_rent_segments(own, ptype)
    if values:
        return median(values), 'delegation'
    values = _latest_rent_segments(in_gov, ptype)
    if values:
        return median(values), 'governorate'
    return None, 'none'
