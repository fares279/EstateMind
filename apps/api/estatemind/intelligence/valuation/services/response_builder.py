"""
Assembles the final API response payload from individual service outputs.
"""
from .labels import model_label, user_reasons

CLIMATE_SOURCE_LABELS = {
    'delegation_composite_score': 'Local climate score for this delegation',
    'kriging': 'Climate score interpolated from nearby delegations',
    'national_average_fallback': 'National average (no local climate score available)',
}


def _format_model_version(model_name: str) -> str:
    """
    Format raw model names to user-friendly labels.
    Examples:
      'bytype__apartment__catboost' → 'CatBoost Apartment Model'
      'ensemble_v2' → 'Ensemble V2'
      'catboost' → 'CatBoost'
    """
    if not model_name or not isinstance(model_name, str):
        return 'Model'
    
    # Split on double underscores
    parts = model_name.lower().split('__')
    
    # Filter and clean parts
    meaningful_parts = []
    for p in parts:
        if p and p != 'bytype':  # Skip 'bytype' prefix
            meaningful_parts.append(p)
    
    if not meaningful_parts:
        return 'Model'
    
    # Format each part
    formatted = []
    for part in meaningful_parts:
        if part == 'catboost':
            formatted.append('CatBoost')
        elif part == 'ensemble':
            formatted.append('Ensemble')
        else:
            formatted.append(part.replace('_', ' ').title())
    
    return ' '.join(formatted) + (' Model' if len(formatted) > 1 else '')


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
    cv_signals_applied: bool = False,
    text_signals_applied: bool = False,
    prediction_source: str | None = None,
    model_version=None,
    snapshot_date=None,
    property_image_result: dict | None = None,
    counterfactuals: list | None = None,
    climate_source: str | None = None,
) -> dict:
    estimated = int(prediction.get('estimated_price', 0))
    ppm2 = float(prediction.get('price_per_m2', 0))
    
    # Signal code translation dictionary
    SIGNAL_CODE_TRANSLATION = {
        'ood:processor_unavailable': 'Image analysis service temporarily unavailable',
        'ood:text_quality_poor': 'Property description too brief for analysis',
        'reference_dataset_missing': 'No comparable properties in this market',
    }
    
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
            # Translate signal codes to user-friendly messages
            translated = SIGNAL_CODE_TRANSLATION.get(w, w)
            internal_warnings.append(translated)
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
        # plain sentences only; pipeline codes (e.g. 'reference_dataset_missing') are dropped
        'uncertainty_reasons': user_reasons(confidence_result.get('uncertainty_reasons', [])),
        'signal_breakdown':    confidence_result.get('signal_breakdown', {}),

        # Feature attribution
        'features_impact': shap_result.get('features_impact', []),
        'shap':            shap_result.get('shap', {}),
        'top_drivers': [
            {
                'feature': item.get('feature'),
                'impact_tnd': round(float(item.get('impact', 0) or 0)),
                'direction': item.get('direction', 'positive'),
                'percent': item.get('percent', 0),
            }
            for item in shap_result.get('features_impact', [])[:5]
        ],

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
        'image_contribution': {
            'available': bool((property_image_result or {}).get('available')),
            'condition_score': (property_image_result or {}).get('condition_score'),
            'image_confidence': (property_image_result or {}).get('image_confidence'),
            'images_used': (property_image_result or {}).get('images_used', 0),
            'images_rejected': (property_image_result or {}).get('images_rejected', 0),
        },

        # Prediction metadata
        'prediction_mode': prediction.get('prediction_mode', 'heuristic'),
        'prediction_source': prediction_source or 'unknown',
        'sentiment_mode':  text_analysis.get('sentiment_mode', 'neutral_fallback'),
        'cv_mode':         image_analysis.get('cv_mode', 'no_cv') if image_analysis else 'no_cv',
        'vision_guidance': [],
        # Expose only user-facing warnings; internal telemetry is suppressed
        'warnings':        user_reasons(user_warnings),
        'climate_source': climate_source or 'unknown',  # Audit trail for climate data provenance
        'model_info': {
            'mode':    prediction.get('prediction_mode', 'heuristic'),
            'version': getattr(model_version, 'version', prediction.get('model_info', {}).get('version', '2.0.0')),
            'name': _format_model_version(getattr(model_version, 'model_name', prediction.get('model_info', {}).get('name', ''))),
            'source': prediction_source or 'unknown',
            # whether the signal moved the price (it is reported either way)
            'cv_signals_applied': cv_signals_applied,
            'text_signals_applied': text_signals_applied,
            'cv_signal_values': cv_analysis_signals or {},
            'text_signal_values': text_analysis_signals or {},
            'note':
                ('Powered by trained valuation models and local market priors'
                + (', adjusted by image and description analysis' if (cv_signals_applied or text_signals_applied) else '')
                + '.'
                if prediction.get('prediction_mode', '').startswith(('catboost', 'fallback_model'))
                else 'Using calibrated market priors.'),
        },
        'provenance': {
            'model_name': getattr(model_version, 'model_name', None),
            'model_version': getattr(model_version, 'version', None),
            'training_date': getattr(model_version, 'training_date', None).isoformat() if getattr(model_version, 'training_date', None) else None,
            'eval_rmse': getattr(model_version, 'eval_rmse', None),
            'eval_r2': getattr(model_version, 'eval_r2', None),
            'eval_mape': getattr(model_version, 'eval_mape', None),
            'data_vintage': snapshot_date.isoformat() if snapshot_date else None,
            'climate_source': climate_source or 'unknown',  # Climate data source for audit
            'climate_source_label': CLIMATE_SOURCE_LABELS.get(climate_source or '', None),
        },
        # e.g. 'CatBoost (Apartment model), trained 2026-09-27'; raw names stay in provenance
        'model_display_name': model_label(
            getattr(model_version, 'model_name', None), getattr(model_version, 'version', None),
            getattr(model_version, 'training_date', None)),
        'counterfactuals': counterfactuals or [],
        'confidence_pct': confidence_result.get('confidence', 50),
        'confidence_band': {
            'low': confidence_result.get('lower_bound', estimated),
            'high': confidence_result.get('upper_bound', estimated),
        },
        'confidence_label': confidence_result.get('confidence_level', 'Medium').upper(),
        'model_version': getattr(model_version, 'version', None),
        'model_name': getattr(model_version, 'model_name', None),
        'data_vintage': snapshot_date.isoformat() if snapshot_date else None,

        # UI flags and notifications (popups)
        'user_notifications': [],
        # Frontend should hide any intelligence window when present
        'intelligence_window': False,

        # Scenario simulation
        'scenarios':       scenarios or [],
        'recommendations': recommendations or [],
    }
