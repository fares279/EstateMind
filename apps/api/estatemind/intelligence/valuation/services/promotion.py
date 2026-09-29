from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from estatemind.intelligence.valuation.models import ValuationModelVersion
from estatemind.intelligence.valuation.services.shap_stability_tester import SHAPStabilityTester

CANONICAL_TEST_PROPERTY = {
    'property_type': 'apartment',
    'transaction_type': 'sale',
    'governorate': 'Tunis',
    'delegation': 'El Menzah',
    'city': 'El Menzah',
    'size_m2': 120,
    'bedrooms': 2,
    'bathrooms': 1,
    'condition': 'good',
    'has_pool': False,
    'has_garden': False,
    'has_parking': True,
    'sea_view': False,
    'elevator': True,
    'description': 'Bright apartment near amenities',
    'image_count': 0,
}

# Each by-type model is tested on its own kind of property.
_REQUEST_TYPE = {'appartement': 'apartment', 'maison': 'house', 'terrain': 'land'}
CANONICAL_BY_TYPE = {
    'maison': {'size_m2': 250, 'bedrooms': 4, 'bathrooms': 2},
    'terrain': {'size_m2': 500, 'bedrooms': 0, 'bathrooms': 0},
}

FEATURE_NAMES = [
    'property_type',
    'transaction_type',
    'governorate',
    'delegation',
    'city',
    'size_m2',
    'bedrooms',
    'bathrooms',
    'condition',
    'has_pool',
    'has_garden',
    'has_parking',
    'sea_view',
    'elevator',
    'description',
    'image_count',
]


@dataclass
class PromotionResult:
    version: ValuationModelVersion
    stability_report: dict[str, Any]
    promoted: bool
    reason: str


class ValuationPromotionGate:
    """Enforces SHAP stability and RMSE gates before champion promotion."""

    RMSE_TOLERANCE_PCT = 2.0

    def run(self, version: ValuationModelVersion, model: Any, champion: ValuationModelVersion | None = None) -> dict[str, Any]:
        """`model` is the version's ModelHandle (what both callers pass). The
        stability check runs on the served bundle, as users would get it."""
        from .model_registry import ValuationModelRegistry

        handle = ValuationModelRegistry().maybe_load_bundle(model)
        bundle = getattr(handle, 'bundle', None)
        if bundle is None:
            return {'promoted': False, 'reason': 'The model could not be loaded for serving', 'stability_report': {}}
        scope = version.model_name.split(':', 1)[-1]
        model_type = scope if scope in _REQUEST_TYPE else 'appartement'
        stability = SHAPStabilityTester().run_served_stability_test(
            bundle,
            {**CANONICAL_TEST_PROPERTY, **CANONICAL_BY_TYPE.get(model_type, {}), 'property_type': _REQUEST_TYPE[model_type]},
            model_property_type=model_type,
        )
        if stability['status'] == 'fail':
            return {
                'promoted': False,
                'reason': 'SHAP stability check failed',
                'stability_report': stability,
            }

        if champion and champion.eval_rmse and version.eval_rmse:
            allowed = champion.eval_rmse * (1 + self.RMSE_TOLERANCE_PCT / 100.0)
            if version.eval_rmse > allowed:
                return {
                    'promoted': False,
                    'reason': (
                        f"Challenger RMSE ({version.eval_rmse:,.0f}) exceeds "
                        f"champion RMSE ({champion.eval_rmse:,.0f}) by more than {self.RMSE_TOLERANCE_PCT:.0f}%"
                    ),
                    'stability_report': stability,
                }

        return {
            'promoted': True,
            'reason': 'Promotion gates passed',
            'stability_report': stability,
        }
