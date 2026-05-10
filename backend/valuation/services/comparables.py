"""
Comparables service — queries Property Gold layer (DB) and CSV market dataset.
DB results are preferred; CSV comparables fill in when the DB is sparse.
"""
import logging
from . import csv_engine

logger = logging.getLogger(__name__)


def _size_score(ref_size: float, comp_size: float) -> float:
    if not comp_size:
        return 10.0
    delta = abs(ref_size - comp_size) / max(ref_size, 1)
    return max(0.0, 20.0 * (1 - delta / 0.5))


def _bedroom_score(ref_bd, comp_bd) -> float:
    if ref_bd is None or comp_bd is None:
        return 5.0
    diff = abs(int(ref_bd) - int(comp_bd))
    return max(0.0, 10.0 - diff * 3.0)


def _similarity(ref: dict, prop) -> float:
    score = 0.0
    ptype = (getattr(prop, 'property_type', '') or '').lower()
    if ptype == ref.get('property_type', '').lower():
        score += 30

    gov = ''
    try:
        gov = (prop.region.governorate or '').lower() if prop.region_id else ''
    except Exception:
        pass
    if gov and gov == (ref.get('governorate') or '').lower():
        score += 25

    try:
        city = (prop.delegation.name or '').lower() if prop.delegation_id else ''
    except Exception:
        city = ''
    ref_city = (ref.get('delegation') or ref.get('city') or '').lower()
    if city and ref_city and city == ref_city:
        score += 15

    score += _size_score(float(ref.get('size_m2') or 100), float(getattr(prop, 'area_sqm', 0) or 0))
    score += _bedroom_score(ref.get('bedrooms'), getattr(prop, 'bedrooms', None))
    return round(score, 1)


def _difference_summary(ref: dict, prop) -> str:
    parts = []
    ref_size  = float(ref.get('size_m2') or 0)
    comp_size = float(getattr(prop, 'area_sqm', 0) or 0)
    if comp_size and ref_size:
        d = comp_size - ref_size
        if abs(d) > 5:
            parts.append(f"{'Larger' if d > 0 else 'Smaller'} by {abs(d):.0f} m²")
    ref_bd  = ref.get('bedrooms')
    comp_bd = getattr(prop, 'bedrooms', None)
    if ref_bd and comp_bd and ref_bd != comp_bd:
        parts.append(f"{comp_bd} bedrooms vs your {ref_bd}")
    return '; '.join(parts) if parts else 'Similar profile'


def find(ref: dict, estimated_price: float, limit: int = 4) -> tuple[list, dict]:
    try:
        from core.models import Property
    except ImportError:
        return [], _empty_context()

    ptype    = (ref.get('property_type') or 'apartment').lower()
    gov_raw  = (ref.get('governorate') or '').strip()
    tx_type  = (ref.get('transaction_type') or 'sale').lower()
    size_m2  = float(ref.get('size_m2') or 100)

    qs = Property.objects.select_related('region', 'delegation').filter(
        is_active=True, price__isnull=False, price__gt=0,
        transaction_type=tx_type, property_type=ptype,
    )
    if gov_raw:
        qs = qs.filter(region__governorate__iexact=gov_raw)

    # Size window ±60%
    qs = qs.filter(area_sqm__gte=size_m2 * 0.40, area_sqm__lte=size_m2 * 1.60)
    candidates = list(qs.order_by('-updated_at')[:200])

    scored = sorted([(p, _similarity(ref, p)) for p in candidates], key=lambda x: x[1], reverse=True)

    all_prices:  list[float] = []
    prices_ppm2: list[float] = []
    for prop, _ in scored[:50]:
        price = float(prop.price or 0)
        area  = float(prop.area_sqm or 1)
        if price > 0:
            all_prices.append(price)
            if area > 0:
                prices_ppm2.append(price / area)

    comparables = []
    for prop, sim in scored[:limit]:
        price = float(prop.price or 0)
        area  = float(prop.area_sqm or 1)
        ppm2  = round(price / area) if area else None
        try:
            gov_name  = prop.region.governorate if prop.region_id else gov_raw
        except Exception:
            gov_name = gov_raw
        try:
            city_name = prop.delegation.name if prop.delegation_id else ''
        except Exception:
            city_name = ''
        comparables.append({
            'title':        (prop.title or '')[:80],
            'price':        round(price),
            'price_per_m2': ppm2,
            'size_m2':      round(float(prop.area_sqm or 0), 1),
            'bedrooms':     getattr(prop, 'bedrooms', None),
            'bathrooms':    getattr(prop, 'bathrooms', None),
            'governorate':  gov_name,
            'city':         city_name,
            'condition':    getattr(prop, 'condition', None),
            'source':       getattr(prop, 'source', ''),
            'similarity':   round(sim),
            'difference':   _difference_summary(ref, prop),
        })

    # Supplement with CSV comparables when DB is sparse
    if len(comparables) < limit:
        csv_comps = csv_engine.find_comparables(ref, limit=limit - len(comparables))
        existing_prices = {c['price'] for c in comparables}
        for c in csv_comps:
            if c['price'] not in existing_prices:
                comparables.append(c)
                existing_prices.add(c['price'])
                if c['price_per_m2']:
                    prices_ppm2.append(c['price_per_m2'])
                if c['price']:
                    all_prices.append(c['price'])

    return comparables, _market_context(prices_ppm2, all_prices, estimated_price)


def _market_context(prices_ppm2: list, all_prices: list, estimated_price: float) -> dict:
    if not prices_ppm2:
        return _empty_context()
    avg_ppm2 = sum(prices_ppm2) / len(prices_ppm2)
    pos = 'above_market' if estimated_price / max(avg_ppm2, 1) > 1.10 else \
          'below_market' if estimated_price / max(avg_ppm2, 1) < 0.90 else 'at_market'
    clean = [p for p in all_prices if p > 0]
    return {
        'avg_price_per_m2': round(avg_ppm2),
        'comparable_count': len(prices_ppm2),
        'price_range':      {'min': round(min(clean)) if clean else None, 'max': round(max(clean)) if clean else None},
        'market_trend':     'stable',
        'price_position':   pos,
        'market_direction': 'Stable market with moderate listing activity.',
    }


def _empty_context() -> dict:
    return {
        'avg_price_per_m2': None, 'comparable_count': 0,
        'price_range':      {'min': None, 'max': None},
        'market_trend':     'unknown', 'price_position': 'unknown',
        'market_direction': 'Insufficient data to assess market direction.',
    }
