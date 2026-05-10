"""
Assembles the final API response payload from individual service outputs.
"""


def build(
    data: dict,
    prediction: dict,
    confidence_result: dict,
    shap_result: dict,
    comparables: list,
    market_context: dict,
    text_analysis: dict,
    ai_explanation: str,
    image_analysis: dict | None = None,
    scenarios: list | None = None,
    recommendations: list | None = None,
    cv_analysis_signals: dict | None = None,
    text_analysis_signals: dict | None = None,
    prediction_source: str | None = None,
) -> dict:
    estimated = int(prediction.get('estimated_price', 0))
    ppm2 = float(prediction.get('price_per_m2', 0))
    # Filter internal warnings so users don't see internal telemetry
    internal_prefixes = (
        "catboost_signal_adjustment_",
        "cv_images_analyzed_",
    )
    internal_exact = (
        "reference_dataset_missing",
        "ood:processor_unavailable",
        "ood:text_quality_poor",
    )

    raw_warnings = prediction.get('warnings', []) or []
    user_warnings = []
    internal_warnings = []
    for w in raw_warnings:
        if any(w.startswith(p) for p in internal_prefixes) or w in internal_exact or (isinstance(w, str) and w.startswith('ood:')):
            internal_warnings.append(w)
        else:
            user_warnings.append(w)

    # Log internal warnings for operators
    if internal_warnings:
        import logging

        logger = logging.getLogger(__name__)
        logger.debug("Internal model warnings suppressed from user output: %s", internal_warnings)

    return {
        # Price predictions
        'estimated_price': estimated,
        'lower_bound':     confidence_result.get('lower_bound', estimated),
        'upper_bound':     confidence_result.get('upper_bound', estimated),
        'price_per_m2':    round(ppm2),
        'currency':        'TND',
        'transaction_type': data.get('transaction_type', 'sale'),

        # Confidence
        'confidence':          confidence_result.get('confidence', 50),
        'confidence_level':    confidence_result.get('confidence_level', 'Medium'),
        'uncertainty_ratio':   confidence_result.get('uncertainty_ratio', 0.14),
        'uncertainty_mode':    confidence_result.get('uncertainty_mode', 'fallback'),
        'uncertainty_reasons': confidence_result.get('uncertainty_reasons', []),
        'signal_breakdown':    confidence_result.get('signal_breakdown', {}),

        # Feature attribution
        'features_impact': shap_result.get('features_impact', []),
        'shap':            shap_result.get('shap', {}),

        # Market evidence
        'comparables':     comparables,
        'market_context':  market_context,

        # Explainability
        'ai_explanation':  ai_explanation,
        'explanation_mode': 'model_based' if prediction.get('prediction_mode', '').startswith(('catboost', 'fallback_model')) else 'rule_based',

        # Text & Vision analysis
        'text_analysis':  text_analysis,
        'image_analysis': image_analysis or {
            'image_count':    0,
            'quality_score':  0.0,
            'coverage_score': 0.0,
            'status':         'no_images',
            'image_analysis': 'No images uploaded.',
        },

        # Prediction metadata
        'prediction_mode': prediction.get('prediction_mode', 'heuristic'),
        'prediction_source': prediction_source or 'unknown',
        'sentiment_mode':  text_analysis.get('sentiment_mode', 'neutral_fallback'),
        'cv_mode':         image_analysis.get('cv_mode', 'no_cv') if image_analysis else 'no_cv',
        'vision_guidance': [],
        # Expose only user-facing warnings; internal telemetry is suppressed
        'warnings':        user_warnings,
        'model_info': {
            'mode':    prediction.get('prediction_mode', 'heuristic'),
            'version': '2.0.0',
            'source': prediction_source or 'unknown',
            'cv_signals_applied': cv_analysis_signals is not None,
            'text_signals_applied': text_analysis_signals is not None,
            'cv_signal_values': cv_analysis_signals or {},
            'text_signal_values': text_analysis_signals or {},
            'note':    (
                ('Powered by trained valuation models and local market priors'
                + (', enhanced with CV and sentiment analysis' if (cv_analysis_signals or text_analysis_signals) else '')
                + '.')
                if prediction.get('prediction_mode', '').startswith(('catboost', 'fallback_model'))
                else 'Using calibrated market priors.'
            ),
        },

        # UI flags and notifications (popups)
        'user_notifications': [],
        # Frontend should hide any intelligence window when present
        'intelligence_window': False,

        # Scenario simulation
        'scenarios':       scenarios or [],
        'recommendations': recommendations or [],
    }
