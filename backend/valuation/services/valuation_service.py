"""Model-backed valuation orchestrator."""

import logging

from . import comparables, confidence, explanation, response_builder, scenario_service, shap_service

from ..inference.fallback_model import FallbackTabularModelService
from ..inference.model_registry import ModelRegistry
from ..inference.request_mapper import map_request
from ..inference.cv_model import CVModelService
from ..inference.sentiment_model import SentimentModelService
from . import nlp_service

logger = logging.getLogger(__name__)


def estimate(data: dict, image_files: list | None = None) -> dict:
    """
    End-to-end valuation pipeline.
    data         — validated dict from ValuationInputSerializer.
    image_files  — list of InMemoryUploadedFile objects (may be empty).
    """
    image_files = image_files or []
    mapped = map_request(data)
    registry = ModelRegistry()
    fallback_service = FallbackTabularModelService()
    cv_service = CVModelService()
    sentiment_service = SentimentModelService()

    # 0a ── Pre-analysis: Image analysis (CV model) - extract signals for price model
    image_analysis = None
    cv_prediction = None
    cv_analysis_signals = None
    if image_files:
        try:
            cv_prediction = cv_service.analyze_images(image_files)
            if cv_prediction:
                cv_analysis_signals = {
                    'image_count': len(image_files),
                    'quality_score': cv_prediction.image_quality_score,
                    'coverage_score': cv_prediction.coverage_score,
                    'confidence': cv_prediction.confidence,
                }
                image_analysis = {
                    'image_count': len(image_files),
                    'property_type_predicted': cv_prediction.property_type,
                    'quality_score': cv_prediction.image_quality_score,
                    'coverage_score': cv_prediction.coverage_score,
                    'confidence': cv_prediction.confidence,
                    'status': cv_prediction.status,
                    'cv_mode': 'vision_enabled',
                    'image_analysis': f"Analyzed {len(image_files)} image(s), predicted property type: {cv_prediction.property_type}",
                    'warnings': cv_prediction.warnings,
                }
        except Exception as exc:
            logger.warning("CV analysis failed: %s", exc)
            image_analysis = {
                'image_count': len(image_files),
                'quality_score': 0.0,
                'coverage_score': 0.0,
                'status': 'analysis_failed',
                'cv_mode': 'vision_error',
                'image_analysis': 'Image analysis failed',
                'warnings': [str(exc)],
            }
    
    if not image_analysis:
        image_analysis = {
            'image_count': 0,
            'quality_score': 0.0,
            'coverage_score': 0.0,
            'status': 'no_images',
            'cv_mode': 'not_used',
            'image_analysis': 'No images uploaded.',
            'warnings': [],
        }

    # 0b ── Pre-analysis: Sentiment analysis (text model) - extract signals for price model
    text_analysis = None
    sentiment_prediction = None
    text_analysis_signals = None
    try:
        description = data.get('description', '')
        sentiment_prediction = sentiment_service.analyze_description(description)
        if sentiment_prediction:
            location_sentiment = nlp_service.analyze_location(data.get('city', ''), data.get('governorate', ''))
            text_analysis_signals = {
                'sentiment_score': sentiment_prediction.sentiment_score,
                'sentiment_label': sentiment_prediction.sentiment_label,
                'description_quality': sentiment_prediction.description_quality,
            }
            text_analysis = {
                'description_quality': sentiment_prediction.description_quality,
                'description_sentiment': sentiment_prediction.sentiment_score,
                'description_sentiment_label': sentiment_prediction.sentiment_label,
                'sentiment_score': sentiment_prediction.sentiment_score,
                'sentiment_label': sentiment_prediction.sentiment_label,
                'location_sentiment': location_sentiment,
                'location_sentiment_label': location_sentiment.get('label', 'neutral'),
                'marketing_effectiveness': 'Evaluated' if description else 'Not evaluated',
                'key_phrases': sentiment_prediction.key_phrases,
                'token_count': sentiment_prediction.token_count,
                'description_score': sentiment_prediction.description_score,
                'sentiment_mode': 'tfidf_enabled',
                'warnings': sentiment_prediction.warnings,
            }
    except Exception as exc:
        logger.warning("Sentiment analysis failed: %s", exc)
    
    if not text_analysis:
        location_sentiment = nlp_service.analyze_location(data.get('city', ''), data.get('governorate', ''))
        text_analysis = {
            'description_quality': 'Not evaluated',
            'description_sentiment': 0.5,
            'description_sentiment_label': 'neutral',
            'sentiment_score': 0.5,
            'sentiment_label': 'neutral',
            'location_sentiment': location_sentiment,
            'location_sentiment_label': location_sentiment.get('label', 'neutral'),
            'marketing_effectiveness': 'Not evaluated',
            'key_phrases': [],
            'token_count': 0,
            'description_score': 0,
            'sentiment_mode': 'not_used',
            'warnings': [],
        }

    # 1 ── Price prediction (primary CatBoost bundle with CV/text signals)
    handle = registry.get_best_handle(mapped.get("model_property_type", mapped.get("property_type", "")))
    logger.info("Model handle retrieved: %s", handle)
    
    if handle is not None:
        logger.info("Loading bundle for handle: scope=%s, property_type=%s, path=%s", handle.scope, handle.property_type, handle.path)
        handle = registry.maybe_load_bundle(handle)
        logger.info("Bundle load result: bundle_available=%s, bundle_error=%s, load_error=%s", 
                    handle.bundle_available if handle else None, 
                    handle.bundle_error if handle else None,
                    handle.load_error if handle else None)
    else:
        logger.warning("No model handle found for property type: %s", mapped.get("model_property_type", mapped.get("property_type", "")))
        handles = registry.list_handles()
        logger.info("Available handles: %s", [(h.scope, h.property_type, h.path) for h in handles])
    
    prediction = None
    prediction_source = "none"
    
    if handle is not None and handle.bundle_available and handle.bundle is not None:
        try:
            logger.info("Predicting with CatBoost bundle (scope=%s, property_type=%s)", handle.scope, handle.property_type)
            pred = handle.bundle.predict(
                mapped,
                {"avg_price_per_m2": 1450},
                cv_analysis=cv_analysis_signals,
                text_analysis=text_analysis_signals,
            )
            prediction = {
                "estimated_price": pred.estimated_price,
                "price_per_m2": pred.price_per_m2,
                "prediction_mode": pred.prediction_mode,
                "warnings": getattr(pred, "warnings", []),
                "uncertainty_reasons": getattr(pred, "uncertainty_reasons", []),
                "model_info": getattr(pred, "model_info", {}),
                "cv_signals": cv_analysis_signals,
                "text_signals": text_analysis_signals,
            }
            prediction_source = "catboost_bundle"
            logger.info("CatBoost prediction successful: price=%s, mode=%s", pred.estimated_price, pred.prediction_mode)
        except Exception as exc:
            logger.error("Primary bundle prediction failed: %s", exc, exc_info=True)
    else:
        logger.warning("Bundle not available or None: handle=%s, bundle_available=%s, bundle=%s", 
                      handle is not None, 
                      handle.bundle_available if handle else None, 
                      handle.bundle if handle else None)

    # 1b ── Fallback: tabular model if primary failed (but prefer CatBoost)
    if prediction is None:
        logger.warning("Falling back to FallbackTabularModelService (CatBoost bundle unavailable)")
        fb = fallback_service.predict(mapped)
        if fb is not None:
            prediction = {
                "estimated_price": fb.estimated_price,
                "price_per_m2": fb.price_per_m2,
                "prediction_mode": fb.prediction_mode,
                "warnings": getattr(fb, "warnings", []),
                "uncertainty_reasons": getattr(fb, "uncertainty_reasons", []),
                "model_info": getattr(fb, "model_info", {}),
                "cv_signals": cv_analysis_signals,
                "text_signals": text_analysis_signals,
            }
            prediction_source = "fallback_tabular"

    if prediction is None:
        raise RuntimeError("No valuation model artifacts could be loaded from the repository")
    logger.info(
        "Valuation complete: gov=%s type=%s size=%s mode=%s price=%s source=%s cv_signals=%s text_signals=%s",
        data.get('governorate', ''),
        data.get('property_type', ''),
        data.get('size_m2', ''),
        prediction['prediction_mode'],
        prediction['estimated_price'],
        prediction_source,
        cv_analysis_signals is not None,
        text_analysis_signals is not None,
    )

    # 4 ── Comparables + market context
    comps, market_ctx = comparables.find(data, prediction['estimated_price'])

    # 5 ── Price drivers, confidence scoring, and scenarios
    shap_result = shap_service.explain(data, prediction, market_ctx, text_analysis, cv_analysis_signals)
    conf_result = confidence.compute(data, prediction, comps, image_files)
    scenarios, recommendations = scenario_service.generate(
        data,
        prediction['estimated_price'],
        comps,
        conf_result,
        text_analysis,
        shap_result.get('features_impact', []),
    )

    # Override bounds
    prediction['lower_bound'] = conf_result['lower_bound']
    prediction['upper_bound'] = conf_result['upper_bound']

    # 6 ── Explanation (with CV and sentiment signals)
    ai_text = explanation.build(
        data,
        prediction,
        conf_result,
        comps,
        market_ctx,
        text_analysis,
        shap_result,
        image_analysis=image_analysis,
        cv_signals=cv_analysis_signals,
        text_signals=text_analysis_signals,
        prediction_source=prediction_source,
    )

    result = response_builder.build(
        data, prediction, conf_result, shap_result,
        comps, market_ctx, text_analysis, ai_text,
        image_analysis=image_analysis,
        scenarios=scenarios,
        recommendations=recommendations,
        cv_analysis_signals=cv_analysis_signals,
        text_analysis_signals=text_analysis_signals,
        prediction_source=prediction_source,
    )

    # User notifications: popup messages for important user-facing events
    notifications = []
    # If property type was normalized/mapped, notify user via popup
    input_type = data.get('property_type')
    mapped_type = mapped.get('model_property_type')
    if input_type and mapped_type and str(input_type).strip().lower() != str(mapped_type).strip().lower():
        notifications.append({
            'type': 'popup',
            'title': 'Property type mapped',
            'message': f"Input property type '{input_type}' was interpreted as '{mapped_type}' for model selection.",
        })

    # Notify user if fallback model used
    if prediction_source == 'fallback_tabular' or prediction.get('prediction_mode', '').startswith('fallback'):
        notifications.append({
            'type': 'popup',
            'title': 'Fallback model used',
            'message': 'The service used a fallback tabular model because the primary CatBoost bundle was unavailable.',
        })

    # Merge notifications into response
    if notifications:
        result.setdefault('user_notifications', [])
        result['user_notifications'].extend(notifications)

    # Ensure intelligence window is disabled client-side
    result['intelligence_window'] = False
    return result
