"""
Confidence scoring — 5-signal weighted blend.
  0.35 × base_quality + 0.25 × input_completeness
  + 0.15 × image_coverage + 0.10 × text_score + 0.15 × comparable_score
Clamped [30, 92].
"""

_MODE_QUALITY = {
    'catboost_by_type': 0.92,
    'catboost_global':  0.80,
    'market_data':      0.72,   # CSV data-driven — real data, no trained model
    'fallback_model':   0.68,
    'heuristic':        0.52,
}

_LEVELS = [
    (80, 'High'),
    (65, 'Medium'),
    (0,  'Low'),
]

_UNCERTAINTY_BY_MODE = {
    'catboost_by_type': 0.08,
    'catboost_global':  0.10,
    'market_data':      0.11,
    'fallback_model':   0.12,
    'heuristic':        0.14,
}


def compute(data: dict, prediction: dict, comparables: list, image_files: list | None = None) -> dict:
    mode            = prediction.get('prediction_mode', 'heuristic')
    estimated_price = float(prediction.get('estimated_price', 0))

    # Signal 1 — base model quality
    base_quality = _MODE_QUALITY.get(mode, 0.52)

    # Signal 2 — input completeness
    req_fields = ['property_type', 'governorate', 'size_m2']
    opt_fields = ['bedrooms', 'bathrooms', 'condition', 'delegation', 'city', 'description', 'transaction_type']
    req_ok = sum(1 for f in req_fields if data.get(f))
    opt_ok = sum(1 for f in opt_fields if data.get(f))
    completeness = (req_ok / len(req_fields)) * 0.6 + (opt_ok / len(opt_fields)) * 0.4

    # Signal 3 — image coverage
    n_images = len(image_files) if image_files else int(data.get('image_count', 0) or 0)
    image_score = min(n_images / 4.0, 1.0)

    # Signal 4 — text quality
    desc = str(data.get('description') or '')
    tokens = [w for w in desc.lower().split() if len(w) > 2]
    richness = min(len(tokens) / 40.0, 1.0)
    text_score = richness * 0.7 + (0.3 if len(tokens) > 10 else 0.0)

    # Signal 5 — comparable support
    comp_score = min(len(comparables) / 4.0, 1.0)

    combined = (
        0.35 * base_quality
        + 0.25 * completeness
        + 0.15 * image_score
        + 0.10 * text_score
        + 0.15 * comp_score
    )

    # OOD penalty
    ood_penalty = len(prediction.get('warnings', [])) * 0.03
    combined = max(0.0, combined - ood_penalty)

    confidence = int(round(max(30, min(92, combined * 100))))

    level = 'Low'
    for threshold, label in _LEVELS:
        if confidence >= threshold:
            level = label
            break

    # Price bounds
    uncertainty_ratio = _UNCERTAINTY_BY_MODE.get(mode, 0.14)
    if confidence < 50:
        uncertainty_ratio *= 1.3
    half_w = estimated_price * uncertainty_ratio
    lower_bound = round(estimated_price - half_w)
    upper_bound = round(estimated_price + half_w)

    # Uncertainty reasons
    reasons = list(prediction.get('uncertainty_reasons', []))
    if n_images == 0:
        reasons.append('No images uploaded — visual quality signal unavailable.')
    if not desc or len(desc.strip()) < 20:
        reasons.append('Short or missing description — NLP signal limited.')
    if not comparables:
        reasons.append('No comparable listings found in the Gold layer database.')

    return {
        'confidence':         confidence,
        'confidence_level':   level,
        'lower_bound':        lower_bound,
        'upper_bound':        upper_bound,
        'uncertainty_ratio':  round(uncertainty_ratio, 3),
        'uncertainty_mode':   'calibrated' if mode.startswith('catboost') else 'heuristic_bounds',
        'uncertainty_reasons': reasons,
        'signal_breakdown': {
            'base_quality':     round(base_quality, 3),
            'completeness':     round(completeness, 3),
            'image_score':      round(image_score, 3),
            'text_score':       round(text_score, 3),
            'comparable_score': round(comp_score, 3),
        },
    }
