"""
Price driver service for valuation responses.

The bundled models do not expose native SHAP values at serve time, so this
service derives stable, model-aware drivers from the current request, the
predicted price, and the available market context.
"""

from __future__ import annotations

from typing import Any
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def _impact(feature: str, label: str, value: float, estimated_price: float, positive: bool = True) -> dict[str, Any]:
    percent = abs(value) / max(float(estimated_price), 1.0) * 100.0
    return {
        'feature': label,
        'impact': round(abs(value)),
        'direction': 'positive' if positive else 'negative',
        'percent': round(percent, 1),
        'raw_feature': feature,
    }


def explain(data: dict, prediction: dict, market_context: dict | None = None, text_analysis: dict | None = None, cv_signals: dict | None = None) -> dict:
    """
    Return frontend-ready price drivers and a simple waterfall summary.
    """
    estimated_price = float(prediction.get('estimated_price', 0) or 0)
    market_context = market_context or {}
    text_analysis = text_analysis or {}

    drivers: list[dict[str, Any]] = []

    size_m2 = float(data.get('size_m2') or 0)
    if size_m2 > 0:
        size_value = size_m2 * max(float(prediction.get('price_per_m2', 0) or market_context.get('avg_price_per_m2') or 1450), 1.0)
        drivers.append(_impact('size_m2', 'Property Size', size_value * 0.12, estimated_price, True))

    governorate = str(data.get('governorate') or '').strip()
    avg_ppm2 = float(market_context.get('avg_price_per_m2') or 0)
    if governorate and avg_ppm2:
        drivers.append(_impact('location', 'Location', avg_ppm2 * max(size_m2, 1.0) * 0.10, estimated_price, True))

    condition = str(data.get('condition') or '').strip().lower()
    if condition in {'excellent', 'new'}:
        drivers.append(_impact('condition', 'Condition', estimated_price * 0.08, estimated_price, True))
    elif condition in {'needs renovation', 'poor'}:
        drivers.append(_impact('condition', 'Condition', estimated_price * 0.07, estimated_price, False))

    if bool(data.get('sea_view')):
        drivers.append(_impact('sea_view', 'Sea View', estimated_price * 0.06, estimated_price, True))
    if bool(data.get('has_pool')):
        drivers.append(_impact('has_pool', 'Swimming Pool', estimated_price * 0.05, estimated_price, True))
    if bool(data.get('has_garden')):
        drivers.append(_impact('has_garden', 'Garden', estimated_price * 0.03, estimated_price, True))
    if bool(data.get('has_parking')):
        drivers.append(_impact('has_parking', 'Parking', estimated_price * 0.025, estimated_price, True))
    if bool(data.get('elevator')):
        drivers.append(_impact('elevator', 'Elevator', estimated_price * 0.02, estimated_price, True))

    description_score = float(text_analysis.get('description_score', 0) or 0)
    if description_score > 0:
        drivers.append(_impact('description_quality', 'Description Quality', estimated_price * (0.02 + description_score * 0.04), estimated_price, True))

    # Engineered / market features
    if market_context.get('avg_price_per_m2'):
        drivers.append(_impact('local_avg_price_m2', 'Local Avg Price/m²', float(market_context.get('avg_price_per_m2')) * max(size_m2, 1.0) * 0.05, estimated_price, True))#type:ignore
    if data.get('city') and data.get('governorate'):
        drivers.append(_impact('city_governorate', 'City-Governorate Prior', estimated_price * 0.03, estimated_price, True))

    # CV & sentiment signals contributions (approximate)
    try:
        cv_multiplier = 1.0
        if cv_signals is not None:
            quality_score = float(cv_signals.get('quality_score', 0.5))
            coverage_score = float(cv_signals.get('coverage_score', 0.5))
            cv_multiplier = 1.0 + (coverage_score * 0.1) + (quality_score * 0.05)
            cv_multiplier = min(cv_multiplier, 1.2)
            cv_impact = int(round(estimated_price * (cv_multiplier - 1.0)))
            drivers.append(_impact('cv_signals', 'Image-based signals', cv_impact, estimated_price, cv_impact >= 0))
    except Exception:
        pass

    try:
        if text_analysis:
            sentiment_score = float(text_analysis.get('sentiment_score', text_analysis.get('description_sentiment', 0.5)))
            text_multiplier = 0.95 + (sentiment_score * 0.1)
            if str(text_analysis.get('description_quality', '')).lower() == 'good':
                text_multiplier += 0.05
            text_multiplier = max(0.9, min(text_multiplier, 1.15))
            text_impact = int(round(estimated_price * (text_multiplier - 1.0)))
            drivers.append(_impact('text_signals', 'Description sentiment', text_impact, estimated_price, text_impact >= 0))
    except Exception:
        pass

    comparable_count = int(market_context.get('comparable_count', 0) or 0)
    if comparable_count:
        drivers.append(_impact('comparables', 'Comparable Listings', estimated_price * min(comparable_count / 20.0, 0.05), estimated_price, True))

    if not drivers:
        drivers.append(_impact('property_type', 'Property Type', estimated_price * 0.10, estimated_price, True))

    ranked = sorted(drivers, key=lambda item: item['impact'], reverse=True)[:8]
    running = round(estimated_price * 0.60)
    waterfall_items: list[dict[str, Any]] = []
    for driver in ranked:
        delta = driver['impact'] if driver['direction'] == 'positive' else -driver['impact']
        running += delta
        waterfall_items.append({
            'feature': driver['feature'],
            'delta': round(delta),
            'running': round(running),
        })

    result = {
        'features_impact': ranked,
        'shap': {
            'baseline': round(estimated_price * 0.60),
            'contributions': waterfall_items,
            'predicted': round(estimated_price),
        },
        # Include key phrases and a SHAP-style barplot (base64 PNG)
        'text_key_phrases': text_analysis.get('key_phrases', []),
        'shap_plot': _render_shap_plot(ranked),
    }
    return result


def _render_shap_plot(ranked: list[dict[str, Any]]) -> str:
    """Render a horizontal barplot for ranked feature impacts and return a base64 data URL."""
    if not ranked:
        return ''
    labels = [item['feature'] for item in ranked]
    impacts = [item['impact'] if item['direction'] == 'positive' else -item['impact'] for item in ranked]
    colors = ['#2ca02c' if v >= 0 else '#d62728' for v in impacts]
    fig, ax = plt.subplots(figsize=(8, max(2, len(ranked) * 0.5)))
    y_pos = list(range(len(labels)))
    ax.barh(y_pos, impacts, color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel('Impact (TND)')
    ax.set_title('Feature contributions to estimated price')
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('ascii')
    return f"data:image/png;base64,{b64}"
