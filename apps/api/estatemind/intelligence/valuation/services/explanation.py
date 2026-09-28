"""
Valuation explanations: plain language by default (`build`), with the pipeline
details kept for a collapsible 'technical details' section (`technical_details`).

Only what actually shaped the estimate is described as doing so: the drivers are
the model's own attributions, and description tone and photos are reported as
information only (they do not change the price; see VALUATION_*_PRICE_ADJUSTMENT).
"""
from .labels import model_label

_TYPE_WORDS = {'appartement': 'apartment', 'apartment': 'apartment', 'maison': 'house', 'house': 'house',
               'villa': 'house', 'terrain': 'plot of land', 'land': 'plot of land', 'commercial': 'commercial property'}
_CONFIDENCE_WORDS = {'high': 'high', 'medium': 'moderate', 'low': 'low'}


def _fmt(n) -> str:
    return f"{int(round(float(n))):,}"


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
    """A short plain-language explanation of the estimate."""
    lines = []
    kind = _TYPE_WORDS.get(str(data.get('property_type') or '').lower(), 'property')
    place = ', '.join(p for p in (data.get('city'), data.get('governorate')) if p) or 'Tunisia'
    size_m2 = data.get('size_m2')
    bedrooms = data.get('bedrooms')
    estimated = int(prediction.get('estimated_price', 0) or 0)
    ppm2 = float(prediction.get('price_per_m2', 0) or 0)
    rent = str(data.get('transaction_type') or 'sale').lower() == 'rent'
    conf_word = _CONFIDENCE_WORDS.get(str(confidence.get('confidence_level', 'Medium')).lower(), 'moderate')

    described = ' '.join(filter(None, [f"{bedrooms}-bedroom" if bedrooms else '', kind]))
    size_part = f" of {float(size_m2):.0f} m²" if size_m2 else ''
    lines.append(
        f"We estimate your {described}{size_part} in {place} at **{_fmt(estimated)} TND**"
        f"{' per month' if rent else ''} (about {_fmt(ppm2)} TND/m²), with {conf_word} confidence."
    )

    drivers = [d for d in shap_result.get('features_impact', []) if 'not provided' not in d.get('feature', '')]
    if drivers:
        phrases = [f"{d['feature'].lower()} ({'+' if d['percent'] >= 0 else ''}{d['percent']:.0f}%)" for d in drivers[:2]]
        lines.append(f"What moved this estimate most: {' and '.join(phrases)}, compared with an average listing.")

    avg_ppm2 = market.get('avg_price_per_m2')
    if comparables and avg_ppm2:
        gap = (ppm2 - float(avg_ppm2)) / float(avg_ppm2) * 100 if avg_ppm2 else 0
        position = 'in line with' if abs(gap) < 5 else (f"{abs(gap):.0f}% {'above' if gap > 0 else 'below'}")
        lines.append(
            f"Similar listings nearby average {_fmt(avg_ppm2)} TND/m²; this estimate is {position} that level."
        )
    else:
        lines.append("We found no closely comparable listings nearby, so the estimate relies on the model alone.")

    trend = str(market.get('market_trend') or '').lower()
    if trend in ('rising', 'up', 'growing'):
        lines.append("Prices in this area are expected to rise over the next year.")
    elif trend in ('falling', 'down', 'declining'):
        lines.append("Prices in this area are expected to ease over the next year.")
    elif trend:
        lines.append("Prices in this area are expected to stay broadly stable.")

    if text_analysis.get('description_quality') == 'insufficient':
        lines.append("Your description was too short or unclear to analyse.")
    elif text_analysis.get('sentiment_label') or text_analysis.get('description_sentiment_label'):
        tone = text_analysis.get('description_sentiment_label') or text_analysis.get('sentiment_label')
        lines.append(f"Your description reads as {tone} in tone; this is shown for information and does not "
                     "change the estimate.")

    if image_analysis and int(image_analysis.get('image_count', 0) or 0) > 0:
        lines.append("Your photos were reviewed for information only; they do not change the estimate.")

    lb, ub = confidence.get('lower_bound'), confidence.get('upper_bound')
    if lb and ub:
        lines.append(f"A realistic range is **{_fmt(lb)} – {_fmt(ub)} TND**.")
    return ' '.join(lines)


def technical_details(prediction: dict, model_version, shap_result: dict, text_analysis: dict,
                      image_analysis: dict | None, prediction_source: str | None, climate_source: str | None,
                      confidence: dict) -> list[dict]:
    """Label/value pairs for the 'Show technical details' section."""
    info = prediction.get('model_info', {}) or {}
    rows = [
        ('Model', model_label(getattr(model_version, 'model_name', None) or info.get('name'),
                              getattr(model_version, 'version', None) or info.get('version'),
                              getattr(model_version, 'training_date', None))),
        ('Model registry entry', ' / '.join(filter(None, [getattr(model_version, 'model_name', None),
                                                          getattr(model_version, 'version', None)]))),
        ('Prediction path', {'catboost_bundle': 'CatBoost bundle (per property type)',
                             'fallback_tabular': 'Fallback tabular model'}.get(prediction_source or '', prediction_source)),
        ('Price drivers', 'CatBoost SHAP values for this prediction' if shap_result.get('drivers_available')
         else 'Not available for this model'),
        ('Description analysis', 'Character TF-IDF sentiment model; information only, not applied to the price'
         if text_analysis.get('description_quality') != 'insufficient' else 'Skipped: not enough readable text'),
        ('Photo analysis', 'ResNet50 image classifier; information only, not applied to the price'
         if image_analysis and int(image_analysis.get('image_count', 0) or 0) > 0 else 'No photos uploaded'),
        ('Climate data', {'delegation_composite_score': 'Local delegation climate score',
                          'national_average_fallback': 'National average (no local score)'}.get(climate_source or '',
                                                                                              climate_source)),
        ('Uncertainty method', confidence.get('uncertainty_mode')),
    ]
    return [{'label': label, 'value': value} for label, value in rows if value]
