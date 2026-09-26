"""
Model-aware explanation builder for valuation responses.
"""


def build(
    data: dict,
    prediction: dict,
    confidence: dict,
    comparables: list,
    market: dict,
    text_analysis: dict,
    shap_result: dict,
    image_analysis: dict | None = None,
    cv_signals: dict | None = None,
    text_signals: dict | None = None,
    prediction_source: str | None = None,
) -> str:
    """Return a human-readable explanation string grounded in the active models."""
    lines = []

    prop_type    = (data.get('property_type') or 'property').title()
    model_type   = (data.get('model_property_type') or prediction.get('model_info', {}).get('property_scope') or data.get('property_type') or 'property')
    model_type   = str(model_type).strip()
    size_m2      = data.get('size_m2')
    governorate  = data.get('governorate') or 'Tunisia'
    city         = data.get('city') or ''
    condition    = (data.get('condition') or 'good').lower()
    transaction  = (data.get('transaction_type') or 'sale').lower()
    bedrooms     = data.get('bedrooms')
    estimated    = int(prediction.get('estimated_price', 0))
    ppm2         = float(prediction.get('price_per_m2', 0))
    conf_level   = confidence.get('confidence_level', 'Medium')
    conf_score   = confidence.get('confidence', 50)
    mode         = prediction.get('prediction_mode', 'heuristic')

    mapped_from = data.get('property_type') or 'property'
    mapped_to = model_type or mapped_from

    # Sentence 0 — model source and signal note (concise)
    model_source_text = "the CatBoost serving bundle" if prediction_source == 'catboost_bundle' else (
        'the fallback tabular model' if prediction_source == 'fallback_tabular' else 'the valuation engine'
    )
    signals_applied = []
    if cv_signals is not None:
        signals_applied.append('computer vision analysis')
    if text_signals is not None:
        signals_applied.append('sentiment analysis')
    signal_part = f" with {' and '.join(signals_applied)}" if signals_applied else ''

    lines.append(f"Using {model_source_text}{signal_part} for this valuation.")

    # Sentence 1 — main estimate
    loc_str = f"{city}, {governorate}" if city else governorate
    tx_str  = 'rental value' if transaction == 'rent' else 'market value'
    size_str = f"{size_m2:.0f} m²" if size_m2 else ''
    room_str = f"{bedrooms}-bedroom " if bedrooms else ''
    lines.append(
        f"Based on your {room_str}{prop_type.lower()}"
        + (f" of {size_str}" if size_str else '')
        + f" in {loc_str}, the estimated {tx_str} is "
        + f"**{estimated:,} TND** (≈ {ppm2:,.0f} TND/m²), "
        + f"with {conf_level.lower()} confidence ({conf_score}/100)."
    )

    # Sentence 2 — top driver
    features = shap_result.get('features_impact', [])
    if features:
        top = features[0]
        direction_word = 'driven up' if top['direction'] == 'positive' else 'pulled down'
        lines.append(
            f"The primary value driver is **{top['feature']}** ({direction_word} by "
            f"≈{top['impact']:,} TND, ~{top['percent']:.1f}% of the estimate)."
        )

    # Sentence 3 — condition + amenities
    cond_notes = []
    if condition in ('new', 'excellent'):
        cond_notes.append(f"the {condition} condition commands a premium")
    elif condition == 'needs renovation':
        cond_notes.append("the renovation needs reduce the estimate")
    amenities = prediction.get('active_amenities', [])
    if amenities:
        labels = {'has_pool': 'pool', 'has_garden': 'garden', 'has_parking': 'parking',
                  'sea_view': 'sea view', 'elevator': 'elevator'}
        amenity_str = ', '.join(labels.get(a, a) for a in amenities[:3])#type:ignore
        cond_notes.append(f"premium features ({amenity_str}) add to the valuation")
    if cond_notes:
        lines.append(f"Additionally, {' and '.join(cond_notes)}.")

    # Sentence 4 — comparables
    n_comp = len(comparables)
    market_trend = market.get('market_trend', 'stable')
    avg_ppm2 = market.get('avg_price_per_m2')
    if n_comp > 0 and avg_ppm2:
        diff = ppm2 - avg_ppm2
        pos_word = 'above' if diff >= 0 else 'below'
        lines.append(
            f"Compared against {n_comp} similar listings, your estimate sits "
            f"{abs(diff):,.0f} TND/m² {pos_word} the local average of {avg_ppm2:,} TND/m². "
            f"The market shows a **{market_trend}** trend."
        )
    else:
        lines.append(
            "No directly comparable listings were found in the database — "
            "the estimate relies fully on market priors for this area."
        )

    # Sentence 5 — text and image signals
    tq = text_analysis.get('description_quality', '')
    if tq and tq != 'None':
        sentiment = text_analysis.get('description_sentiment_label', text_analysis.get('sentiment_label', 'neutral'))
        sentiment_mode = text_analysis.get('sentiment_mode', 'not_used')
        lines.append(
            f"The description signal is **{tq.lower()}** quality with a {sentiment} tone from the {sentiment_mode} text model, "
            f"which {'supports' if sentiment == 'positive' else 'keeps the narrative conservative for'} the listing value."
        )

    if image_analysis:
        cv_mode = image_analysis.get('cv_mode', 'not_used')
        image_count = int(image_analysis.get('image_count', 0) or 0)
        if image_count > 0:
            predicted_type = image_analysis.get('property_type_predicted', 'unknown')
            lines.append(
                f"Uploaded imagery was processed by the {cv_mode} CV path across {image_count} image(s), "
                f"with a predicted property type of {predicted_type}."
            )
        else:
            lines.append("No images were uploaded, so the CV path did not contribute to this valuation.")

    # Sentence 6 — model note
    if mode == 'heuristic':
        lines.append(
            "**Note:** This estimate uses calibrated market priors. Upload property images and add a detailed description to improve coverage."
        )
    elif mode == 'market_data':
        lines.append(
            "**Note:** This estimate is data-driven, using real Tunisian listing medians for this area."
        )
    elif mode.startswith(('catboost', 'fallback_model')):
        lines.append(
            "**Note:** The price engine is driven by the mapped CatBoost serving bundle, with fallback tabular models used only when needed."
        )

    # Sentence 7 — bounds
    lb = confidence.get('lower_bound', 0)
    ub = confidence.get('upper_bound', 0)
    lines.append(
        f"The plausible price range is **{lb:,} – {ub:,} TND** "
        f"(±{int(confidence.get('uncertainty_ratio', 0.14) * 100)}%)."
    )

    return ' '.join(lines)
