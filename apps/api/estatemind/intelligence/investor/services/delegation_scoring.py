"""Rule-based opportunity score for a whole delegation (shared by the investor
opportunities list and the chatbot).

It scores a standard 100 m2 property at the delegation's average price per m2
with the same rule-based scorer the deal scanner uses. It is a comparison
between delegations, not a valuation of any particular property.
"""
from __future__ import annotations

from .scorer import score_listing

STANDARD_SURFACE_M2 = 100.0


def score_delegation(delegation_name: str, governorate: str, price_per_m2: float,
                     property_type: str = 'apartment') -> dict | None:
    price = float(price_per_m2 or 0)
    if price <= 0:
        return None
    scored = score_listing({
        'listing_price_tnd': price * STANDARD_SURFACE_M2,
        'surface_m2': STANDARD_SURFACE_M2,
        'property_type': property_type,
        'governorate': governorate,
        'delegation': delegation_name,
        'room_count': 3,
    })
    return {
        'delegation': delegation_name,
        'governorate': governorate,
        'avg_price_pm2': price,
        'opportunity_score': scored['opportunity_score'],
        'investment_grade': scored['investment_grade'],
        'gross_yield_pct': scored['yield']['gross_yield_pct'],
        'buy_signal': scored['buy_signal']['signal'],
        'forecast_6m_pct': scored['forecast']['forecast_6m_pct'],
        'forecast_12m_pct': scored['forecast']['forecast_12m_pct'],
        'undervaluation': scored['undervaluation']['label'],
        'scoring_method': 'rule_based',
    }
