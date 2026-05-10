"""
Tunisian real estate market estimator.
Uses data-driven priors from actual listings CSV when available,
falling back to hard-coded market priors for commercial / unavailable cases.
"""
from . import csv_engine as _csv

# ── Sale price per m² priors (TND, national base) ───────────────────────────
# Platform types: Apartment | House | Commercial | Land  (4 canonical types).
# House covers all dwelling types including former villa class.
BASE_PRICE_SALE = {
    'apartment':  1_800,
    'house':      2_200,  # blended apartment + detached + former villa
    'commercial': 2_100,
    'land':         420,
}

# ── Monthly rent per m² priors (TND) ────────────────────────────────────────
BASE_PRICE_RENT = {
    'apartment':  8.5,
    'house':     10.5,
    'commercial': 9.5,
    'land':        1.5,
}

# ── Governorate multipliers — keyed by exact DB name (lowercase) ─────────────
GOVERNORATE_MULT = {
    'ariana':      1.35,
    'béja':        0.72,
    'beja':        0.72,
    'ben arous':   1.18,
    'bizerte':     0.88,
    'gabès':       0.80,
    'gabes':       0.80,
    'gafsa':       0.75,
    'jendouba':    0.70,
    'kairouan':    0.78,
    'kasserine':   0.65,
    'kébili':      0.62,
    'kebili':      0.62,
    'la manouba':  0.95,
    'manouba':     0.95,
    'le kef':      0.65,
    'kef':         0.65,
    'mahdia':      0.85,
    'médenine':    0.78,
    'medenine':    0.78,
    'monastir':    1.00,
    'nabeul':      0.98,
    'sfax':        1.10,
    'sidi bouzid': 0.68,
    'siliana':     0.68,
    'sousse':      1.05,
    'tataouine':   0.60,
    'tozeur':      0.72,
    'tunis':       1.65,
    'zaghouan':    0.78,
}

# ── Delegation-level premium/discount relative to governorate (additive) ─────
DELEGATION_ADJ = {
    # Tunis premium quarters
    'carthage':               0.28,
    'la marsa':               0.24,
    'le kram':                0.08,
    'la goulette':            0.12,
    'el menzah':              0.16,
    'el omrane supérieur':    0.05,
    'cité el khadra':         0.04,
    'le bardo':               0.00,
    'sidi hassine':          -0.10,
    'el kabaria':            -0.14,
    'djebel jelloud':        -0.12,
    'séjoumi':               -0.10,
    'médina':                -0.05,
    # Nabeul
    'hammamet':               0.22,   # neighbourhood synonym
    'grombalia':              0.10,
    'soliman':                0.08,
    'korba':                  0.06,
    'kélibia':                0.05,
    'nabeul':                 0.00,
    # Sousse
    'hammam sousse':          0.14,
    'akouda':                 0.10,
    'sousse médina':          0.00,
    'sousse jawhara':         0.06,
    # Monastir
    'monastir':               0.06,
    # Sfax
    'sfax ville':             0.06,
    'sfax sud':               0.00,
    # Médenine / Djerba
    'djerba - houmt souk':    0.22,
    'djerba - midoun':        0.20,
    'djerba - ajim':          0.10,
    'zarzis':                 0.08,
    'ben gardane':           -0.06,
    # Ariana
    'la soukra':              0.10,
    'raoued':                 0.05,
    'ariana ville':           0.08,
    'mnihla':                -0.05,
    'ettadhamen':            -0.08,
    # Ben Arous
    'hammam lif':             0.10,
    'ezzahra':                0.08,
    'rades':                  0.06,
    'radès':                  0.06,
    'el mourouj':             0.04,
    'fouchana':              -0.04,
    # Bizerte
    'bizerte nord':           0.04,
    'ras jebel':              0.02,
}

# ── Condition multipliers ────────────────────────────────────────────────────
CONDITION_ADJ = {
    'new':              0.25,
    'neuf':             0.25,
    'excellent':        0.15,
    'good':             0.05,
    'bon état':         0.05,
    'fair':            -0.05,
    'passable':        -0.05,
    'needs renovation':-0.20,
    'needs_renovation':-0.20,
    'à rénover':       -0.20,
}

# ── Amenity premiums ─────────────────────────────────────────────────────────
AMENITY_ADJ = {
    'has_pool':    0.10,
    'has_garden':  0.08,
    'has_parking': 0.06,
    'sea_view':    0.15,
    'elevator':    0.07,
}

AMENITY_LABELS = {
    'has_pool':    'Swimming Pool',
    'has_garden':  'Garden',
    'has_parking': 'Parking',
    'sea_view':    'Sea View',
    'elevator':    'Elevator',
}

# ── Positive / Negative NLP keywords ────────────────────────────────────────
_POS_KW = [
    'rénové', 'renove', 'renovated', 'neuf', 'new', 'moderne', 'modern',
    'luxe', 'luxury', 'lumineux', 'luminous', 'sécurisé', 'secure',
    'calme', 'quiet', 'vue', 'panoramique', 'panoramic', 'meublé', 'furnished',
    'équipé', 'equipped', 'climatisé', 'air conditioning', 'piscine', 'pool',
    'jardin', 'garden', 'parking', 'terrasse', 'terrace', 'ascenseur',
]
_NEG_KW = [
    'à rénover', 'travaux', 'dégradé', 'vétuste', 'urgent', 'urgente',
    'problème', 'humidité', 'fissure', 'ancien',
]


def _size_factor(size_m2: float, ptype: str) -> float:
    if ptype == 'land':
        if size_m2 < 150:   return 1.20
        if size_m2 < 400:   return 1.08
        if size_m2 < 1_000: return 1.00
        if size_m2 < 5_000: return 0.90
        return 0.80
    else:
        if size_m2 < 50:  return 1.20
        if size_m2 < 80:  return 1.08
        if size_m2 < 150: return 1.00
        if size_m2 < 300: return 0.95
        return 0.88


def _bedroom_factor(bedrooms, size_m2: float) -> float:
    if not bedrooms or not size_m2:
        return 1.0
    density = int(bedrooms) / max(size_m2, 1)
    if density > 0.06:  return 1.06
    if density < 0.02:  return 0.97
    return 1.0


# Legacy type aliases — normalise to canonical 4-type system
_TYPE_ALIAS = {'villa': 'house', 'office': 'commercial', 'farm': 'commercial'}


def estimate(data: dict) -> dict:
    ptype_raw = (data.get('property_type') or 'apartment').lower().strip()
    ptype     = _TYPE_ALIAS.get(ptype_raw, ptype_raw)
    gov_raw   = (data.get('governorate')   or '').strip()
    deleg_raw = (data.get('delegation')    or data.get('city') or '').strip()
    size_m2   = float(data.get('size_m2')  or 120)
    condition = (data.get('condition')     or 'good').lower().strip()
    tx_type   = (data.get('transaction_type') or 'sale').lower().strip()
    bedrooms  = data.get('bedrooms')
    desc      = (data.get('description') or '').lower()

    # 1 — Base price per m² (try CSV data-driven first)
    csv_ppm2 = _csv.get_ppm2(deleg_raw, gov_raw, ptype, tx_type)
    use_csv  = csv_ppm2 is not None and csv_ppm2 > 0

    if use_csv:
        # CSV already encodes all location effects — no gov/deleg mult needed
        base_ppm2  = round(csv_ppm2)
        gov_mult   = 1.0
        deleg_adj  = 0.0
        unknown_gov = False
        prediction_mode = 'market_data'
    else:
        base_ppm2   = (BASE_PRICE_RENT if tx_type == 'rent' else BASE_PRICE_SALE).get(ptype, 1_800)
        gov_key     = gov_raw.lower()
        gov_mult    = GOVERNORATE_MULT.get(gov_key, 0.85)
        unknown_gov = gov_key not in GOVERNORATE_MULT
        deleg_key   = deleg_raw.lower()
        deleg_adj   = DELEGATION_ADJ.get(deleg_key, 0.0)
        prediction_mode = 'heuristic'

    # 2 — Size economy factor
    size_fact = _size_factor(size_m2, ptype)

    # 3 — Condition
    cond_adj = CONDITION_ADJ.get(condition, 0.0)

    # 4 — Bedroom density
    br_fact = _bedroom_factor(bedrooms, size_m2)

    # 5 — Amenities
    active_amenities: dict[str, float] = {}
    if ptype != 'land':
        for field, adj in AMENITY_ADJ.items():
            if data.get(field):
                active_amenities[field] = adj
    amenity_total = sum(active_amenities.values())

    # 6 — NLP description bonus (bounded ±2%)
    pos = sum(1 for kw in _POS_KW if kw in desc)
    neg = sum(1 for kw in _NEG_KW if kw in desc)
    total_kw = pos + neg or 1
    desc_bonus = max(-0.02, min(0.02, (pos - neg) / (total_kw * 5)))

    # 7 — Composite ppm²
    adj_mult = (1 + cond_adj + amenity_total + deleg_adj + desc_bonus) * br_fact
    ppm2     = base_ppm2 * gov_mult * size_fact * adj_mult

    # 8 — Total price
    total = ppm2 * size_m2

    # 9 — Feature contributions (SHAP-like waterfall)
    # National baseline uses hard-coded priors so the waterfall has a stable anchor
    national_ppm2 = (BASE_PRICE_RENT if tx_type == 'rent' else BASE_PRICE_SALE).get(ptype, 1_800)
    base_total    = national_ppm2 * size_m2

    contributions = {
        'size':                national_ppm2 * gov_mult * (size_fact - 1.0) * adj_mult * size_m2,
        'condition':           national_ppm2 * gov_mult * size_fact * cond_adj * br_fact * size_m2,
        'bedroom_layout':      national_ppm2 * gov_mult * size_fact * (br_fact - 1.0) * size_m2 if bedrooms else 0,
        'description_quality': national_ppm2 * gov_mult * size_fact * desc_bonus * size_m2,
    }
    if use_csv:
        # Location premium/discount = difference between CSV median and national baseline
        loc_contribution = (csv_ppm2 - national_ppm2) * size_fact * adj_mult * size_m2
        contributions['location'] = loc_contribution
    else:
        contributions['location'] = national_ppm2 * (gov_mult - 1.0) * size_fact * adj_mult * size_m2
        if deleg_adj != 0:
            contributions['neighbourhood'] = national_ppm2 * gov_mult * size_fact * deleg_adj * size_m2

    for field, adj in active_amenities.items():
        contributions[AMENITY_LABELS[field]] = base_ppm2 * gov_mult * size_fact * adj * size_m2

    # Warnings
    warnings = []
    if unknown_gov:
        warnings.append(f"Governorate '{gov_raw}' not in market priors — using regional average.")
    if size_m2 < 15 or size_m2 > 10_000:
        warnings.append(f"Unusual size ({size_m2:.0f} m²) — estimate may be less reliable.")

    uncertainty_reasons = []
    if not use_csv:
        uncertainty_reasons.append('Price based on market priors — actual listing data unavailable for this area/type.')

    return {
        'estimated_price':   round(total),
        'price_per_m2':      round(ppm2, 1),
        'base_price_per_m2': base_ppm2,
        'gov_multiplier':    gov_mult,
        'deleg_adj':         deleg_adj,
        'size_factor':       size_fact,
        'condition_adj':     cond_adj,
        'amenity_total':     amenity_total,
        'desc_bonus':        desc_bonus,
        'base_total':        round(base_total),
        'contributions':     contributions,
        'active_amenities':  list(active_amenities.keys()),
        'prediction_mode':   prediction_mode,
        'warnings':          warnings,
        'uncertainty_reasons': uncertainty_reasons,
        'csv_ppm2_used':     csv_ppm2,
    }
