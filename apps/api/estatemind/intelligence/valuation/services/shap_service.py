"""Price drivers for valuation responses: per-prediction CatBoost SHAP values."""

from __future__ import annotations

import math

from .labels import feature_label


def explain(data: dict, prediction: dict, market_context: dict | None = None, text_analysis: dict | None = None,
            cv_signals: dict | None = None) -> dict:
    """What the model weighted for this estimate: CatBoost SHAP values.

    The model predicts log(price), so each feature's contribution is a price factor
    exp(phi). Starting from the model's baseline (its average prediction) and
    applying the factors largest first gives TND steps that add up exactly to the
    model's output. The order only affects how a joint effect is split between
    steps, not the total. Coordinates count as one feature ('Map position').

    Without attributions (a model that does not provide them) no drivers are
    returned, rather than invented ones. (This used to return fixed fractions
    of the price, e.g. location = local price x size x 10%, a baseline of 60% of
    the estimate, and 'comparable listings' as a driver.)
    """
    estimated_price = float(prediction.get('estimated_price', 0) or 0)
    attributions = prediction.get('attributions') or {}
    phi = attributions.get('phi') or {}
    if not phi:
        return {'features_impact': [], 'shap': {}, 'drivers_available': False}

    # The baseline is the model's average for this kind of listing: the sale/rent
    # effect is folded in (the champion was trained on sales and rents together,
    # so its raw average is a rent-like 24k TND and 'Sale or rent' read +1,171%).
    base_log = attributions['base_log'] + phi.get('transaction_type', 0.0)
    no_position = data.get('latitude') in (None, '') or data.get('longitude') in (None, '')
    grouped: dict[str, float] = {}
    for feature, value in phi.items():
        if feature == 'transaction_type':
            continue
        label = feature_label(feature)
        if feature in ('latitude', 'longitude') and no_position:
            # the API receives no coordinates; the model sees a filled-in value
            label = 'Map position (not provided)'
        grouped[label] = grouped.get(label, 0.0) + value
    ordered = sorted(grouped.items(), key=lambda item: abs(item[1]), reverse=True)

    baseline = math.expm1(base_log)
    running = baseline
    steps, drivers = [], []
    for label, value in ordered:
        new = (running + 1) * math.exp(value) - 1
        delta = new - running
        running = new
        steps.append({'feature': label, 'delta': round(delta), 'running': round(running)})
        if abs(math.exp(value) - 1) >= 0.005:  # hide effects under 0.5%
            drivers.append({
                'feature': label,
                'impact': round(abs(delta)),
                'direction': 'positive' if delta >= 0 else 'negative',
                'percent': round((math.exp(value) - 1) * 100, 1),
                'raw_feature': label,
            })
    model_price = running
    if estimated_price and abs(estimated_price - model_price) >= 1:
        # anything applied after the model (none by default; see VALUATION_*_PRICE_ADJUSTMENT)
        steps.append({'feature': 'Adjustments after the model', 'delta': round(estimated_price - model_price),
                      'running': round(estimated_price)})
    return {
        'features_impact': drivers[:8],
        'shap': {'baseline': round(baseline), 'contributions': steps, 'predicted': round(estimated_price or model_price),
                 'method': 'catboost_shap',
                 'baseline_label': f"Average {'rental' if data.get('transaction_type') == 'rent' else 'sale'} "
                                   'listing (model baseline)'},
        'drivers_available': True,
    }
