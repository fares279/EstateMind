"""
What-if scenario simulator — generates actionable upgrade scenarios.
Ported from Scrapper agent and adapted for the Django pipeline.
"""
from __future__ import annotations

AMENITY_LABELS = {
    'has_pool':    'swimming pool',
    'has_garden':  'garden',
    'has_parking': 'parking',
    'sea_view':    'sea view',
    'elevator':    'elevator',
}

CONDITION_ORDER = ['needs renovation', 'fair', 'good', 'excellent', 'new']


def _pct(base: int, delta: int) -> float:
    if base <= 0:
        return 0.0
    return round((delta / base) * 100, 2)


def _confidence_from(confidence_result: dict) -> float:
    base = float((confidence_result or {}).get('confidence', 60)) / 100.0
    return max(0.35, min(0.95, base * 0.92 + 0.05))


def _amenity_scenarios(data: dict, estimated_price: int, comparables: list, conf: float) -> list:
    ptype = (data.get('property_type') or '').lower()
    if ptype == 'land':
        return []

    weights = {
        'has_pool':    0.10 if ptype == 'house' else 0.07,
        'has_garden':  0.05,
        'has_parking': 0.035,
        'sea_view':    0.09,
        'elevator':    0.025,
    }
    n_comp = len(comparables)
    results = []
    for field, weight in weights.items():
        if bool(data.get(field)):
            continue
        label = AMENITY_LABELS[field]
        boost = int(round(estimated_price * weight))
        results.append({
            'scenario_name':        f'Add {label}',
            'scenario_description': f'Simulate adding a {label} to the property.',
            'modified_features':    {field: True},
            'predicted_price':      max(1, estimated_price + boost),
            'price_delta':          boost,
            'delta_percentage':     _pct(estimated_price, boost),
            'confidence':           round(conf, 2),
            'why': (
                f'Properties with {label} in this market typically command a premium. '
                f'Based on {n_comp} comparable listing(s).'
            ),
        })
    return results


def _condition_scenario(data: dict, estimated_price: int, conf: float) -> dict | None:
    current = (data.get('condition') or 'good').lower().strip()
    if current not in CONDITION_ORDER:
        current = 'good'
    idx = CONDITION_ORDER.index(current)
    if idx >= len(CONDITION_ORDER) - 1:
        return None
    upgraded = CONDITION_ORDER[idx + 1]
    boost = int(round(estimated_price * 0.045))
    return {
        'scenario_name':        f'Improve condition to {upgraded.title()}',
        'scenario_description': f'Upgrade the property from {current} to {upgraded} condition.',
        'modified_features':    {'condition': upgraded},
        'predicted_price':      max(1, estimated_price + boost),
        'price_delta':          boost,
        'delta_percentage':     _pct(estimated_price, boost),
        'confidence':           round(conf, 2),
        'why': 'Improving condition aligns the listing with stronger comparables and raises buyer willingness.',
    }


def _description_scenario(estimated_price: int, description_score: float, conf: float) -> dict:
    target = 0.82
    lift   = max(target - description_score, 0.0)
    boost  = int(round(estimated_price * lift * 0.12))
    return {
        'scenario_name':        'Improve description quality',
        'scenario_description': 'Write a richer, clearer description with stronger marketing language.',
        'modified_features':    {'description_score': round(target, 2)},
        'predicted_price':      max(1, estimated_price + boost),
        'price_delta':          boost,
        'delta_percentage':     _pct(estimated_price, boost),
        'confidence':           round(conf, 2),
        'why': 'Clearer descriptions typically improve engagement and support a stronger buyer perception.',
    }


def generate(
    data: dict,
    estimated_price: int,
    comparables: list,
    confidence_result: dict,
    text_analysis: dict,
    features_impact: list,
) -> tuple[list, list]:
    """
    Returns (scenario_rows, recommendations).
    scenario_rows  — up to 5 scenario dicts for the API response.
    recommendations — concise summaries for display.
    """
    conf       = _confidence_from(confidence_result)
    desc_score = float((text_analysis or {}).get('description_score', 0.5))

    scenarios = []
    scenarios.extend(_amenity_scenarios(data, estimated_price, comparables, conf))

    cond = _condition_scenario(data, estimated_price, conf)
    if cond:
        scenarios.append(cond)

    scenarios.append(_description_scenario(estimated_price, desc_score, conf))

    # Top feature reinforcement
    if features_impact:
        top = max(features_impact, key=lambda f: abs(f.get('impact', 0) or 0))
        impact_val = int(top.get('impact', 0) or 0)
        if impact_val > 0 and top.get('direction') == 'positive':
            label = top.get('feature', 'key driver')
            boost = int(round(impact_val * 0.25))
            scenarios.append({
                'scenario_name':        f'Reinforce {label}',
                'scenario_description': f'Double down on {label.lower()}, the strongest value driver.',
                'modified_features':    {'focus_feature': label},
                'predicted_price':      max(1, estimated_price + boost),
                'price_delta':          boost,
                'delta_percentage':     _pct(estimated_price, boost),
                'confidence':           round(conf, 2),
                'why': f'{label} is already the primary driver — enhancing it gives the highest upside.',
            })

    # Sort by delta desc, cap at 5
    ordered = sorted(scenarios, key=lambda s: s['price_delta'], reverse=True)[:5]

    recommendations = [
        {
            'title':                  s['scenario_name'],
            'description':            s['scenario_description'],
            'predicted_impact_tnd':   s['price_delta'],
            'predicted_impact_pct':   s['delta_percentage'],
            'confidence':             s['confidence'],
            'justification':          s['why'],
        }
        for s in ordered
    ]
    return ordered, recommendations
