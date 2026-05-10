from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .inference.request_mapper import map_request
from .services import valuation_service


def _payload() -> dict:
    return {
        "property_type": "apartment",
        "governorate": "Tunis",
        "delegation": "La Soukra",
        "city": "La Soukra",
        "transaction_type": "sale",
        "size_m2": 120,
        "bedrooms": 2,
        "bathrooms": 1,
        "description": "Bright apartment near amenities",
        "condition": "good",
        "has_pool": False,
        "has_garden": False,
        "has_parking": True,
        "sea_view": False,
        "elevator": True,
        "image_count": 2,
    }


class RequestMapperTests(SimpleTestCase):
    def test_map_request_uses_serializer_contract(self):
        mapped = map_request(_payload())

        self.assertEqual(mapped["property_type"], "apartment")
        self.assertEqual(mapped["model_property_type"], "appartement")
        self.assertEqual(mapped["transaction_type"], "sale")
        self.assertEqual(mapped["delegation"], "La Soukra")
        self.assertEqual(mapped["city"], "La Soukra")
        self.assertEqual(mapped["surface_m2"], 120.0)
        self.assertEqual(mapped["image_count"], 2)
        self.assertEqual(mapped["input_completeness"], 1.0)


class ValuationServiceModelTests(SimpleTestCase):
    def test_estimate_prefers_model_bundle_over_heuristic(self):
        payload = _payload()
        bundle_prediction = SimpleNamespace(
            estimated_price=450000,
            price_per_m2=3750,
            prediction_mode="catboost_by_type",
            warnings=["bundle_used"],
        )
        fake_bundle = SimpleNamespace(predict=Mock(return_value=bundle_prediction))
        fake_handle = SimpleNamespace(
            bundle_available=True,
            bundle=fake_bundle,
            scope="by_type",
            property_type="appartement",
            path="/path/to/model.joblib",
            bundle_error=None,
            load_error=None,
        )
        fake_registry = SimpleNamespace(
            get_best_handle=Mock(return_value=fake_handle),
            maybe_load_bundle=Mock(side_effect=lambda handle: handle),
        )
        fake_fallback = SimpleNamespace(predict=Mock(return_value=None))

        with (
            patch.object(valuation_service, "ModelRegistry", return_value=fake_registry),
            patch.object(valuation_service, "FallbackTabularModelService", return_value=fake_fallback),
            patch.object(valuation_service.comparables, "find", return_value=([], {"avg_price_per_m2": 3750, "comparable_count": 0})),
            patch.object(valuation_service.confidence, "compute", return_value={
                "lower_bound": 440000,
                "upper_bound": 460000,
                "confidence": 82,
                "confidence_level": "High",
                "uncertainty_ratio": 0.08,
                "uncertainty_mode": "calibrated",
                "uncertainty_reasons": [],
                "signal_breakdown": {},
            }),
            patch.object(valuation_service.response_builder, "build", return_value={"estimated_price": 450000, "price_per_m2": 3750, "prediction_mode": "catboost_by_type", "warnings": ["bundle_used"], "lower_bound": 440000, "upper_bound": 460000, "confidence": 82, "confidence_level": "High"}),
        ):
            result = valuation_service.estimate(payload, [])

        self.assertEqual(result["estimated_price"], 450000)
        self.assertEqual(result["price_per_m2"], 3750)
        self.assertEqual(result["prediction_mode"], "catboost_by_type")
        fake_bundle.predict.assert_called_once()
        fake_registry.get_best_handle.assert_called_once_with("appartement")
        fake_registry.maybe_load_bundle.assert_called_once_with(fake_handle)

    def test_estimate_falls_back_to_tabular_model_when_bundle_missing(self):
        payload = _payload()
        fallback_prediction = SimpleNamespace(
            estimated_price=320000,
            price_per_m2=2667,
            prediction_mode="fallback_model",
            warnings=["fallback_tabular_model_used"],
        )
        fake_handle = SimpleNamespace(
            bundle_available=False,
            bundle=None,
            scope="by_type",
            property_type="appartement",
            path="/path/to/model.joblib",
            bundle_error="Model not found",
            load_error=None,
        )
        fake_registry = SimpleNamespace(
            get_best_handle=Mock(return_value=fake_handle),
            maybe_load_bundle=Mock(side_effect=lambda handle: handle),
        )
        fake_fallback = SimpleNamespace(predict=Mock(return_value=fallback_prediction))

        with (
            patch.object(valuation_service, "ModelRegistry", return_value=fake_registry),
            patch.object(valuation_service, "FallbackTabularModelService", return_value=fake_fallback),
            patch.object(valuation_service.comparables, "find", return_value=([], {"avg_price_per_m2": 2667, "comparable_count": 0})),
            patch.object(valuation_service.confidence, "compute", return_value={
                "lower_bound": 310000,
                "upper_bound": 330000,
                "confidence": 64,
                "confidence_level": "Medium",
                "uncertainty_ratio": 0.12,
                "uncertainty_mode": "calibrated",
                "uncertainty_reasons": [],
                "signal_breakdown": {},
            }),
            patch.object(valuation_service.response_builder, "build", return_value={"estimated_price": 320000, "price_per_m2": 2667, "prediction_mode": "fallback_model", "warnings": ["fallback_tabular_model_used"], "lower_bound": 310000, "upper_bound": 330000, "confidence": 64, "confidence_level": "Medium"}),
        ):
            result = valuation_service.estimate(payload, [])

        self.assertEqual(result["estimated_price"], 320000)
        self.assertEqual(result["price_per_m2"], 2667)
        self.assertEqual(result["prediction_mode"], "fallback_model")
        fake_fallback.predict.assert_called_once()
        fake_registry.get_best_handle.assert_called_once_with("appartement")

    def test_estimate_populates_price_drivers_and_scenarios(self):
        payload = _payload()
        bundle_prediction = SimpleNamespace(
            estimated_price=450000,
            price_per_m2=3750,
            prediction_mode="catboost_by_type",
            warnings=[],
        )
        fake_bundle = SimpleNamespace(predict=Mock(return_value=bundle_prediction))
        fake_handle = SimpleNamespace(
            bundle_available=True,
            bundle=fake_bundle,
            scope="by_type",
            property_type="appartement",
            path="/path/to/model.joblib",
            bundle_error=None,
            load_error=None,
        )
        fake_registry = SimpleNamespace(
            get_best_handle=Mock(return_value=fake_handle),
            maybe_load_bundle=Mock(side_effect=lambda handle: handle),
        )
        fake_fallback = SimpleNamespace(predict=Mock(return_value=None))
        shap_result = {
            "features_impact": [
                {"feature": "Property Size", "impact": 50000, "direction": "positive", "percent": 11.1},
            ],
            "shap": {"baseline": 270000, "contributions": [], "predicted": 450000},
        }
        scenario_rows = [{"scenario_name": "Add sea view", "price_delta": 25000}]
        recommendation_rows = [{"title": "Add sea view", "predicted_impact_tnd": 25000}]

        with (
            patch.object(valuation_service, "ModelRegistry", return_value=fake_registry),
            patch.object(valuation_service, "FallbackTabularModelService", return_value=fake_fallback),
            patch.object(valuation_service.comparables, "find", return_value=([{"price": 1}], {"avg_price_per_m2": 3750, "comparable_count": 1, "market_trend": "stable"})),
            patch.object(valuation_service.shap_service, "explain", return_value=shap_result) as mock_shap,
            patch.object(valuation_service.scenario_service, "generate", return_value=(scenario_rows, recommendation_rows)) as mock_scenarios,
            patch.object(valuation_service.confidence, "compute", return_value={
                "lower_bound": 440000,
                "upper_bound": 460000,
                "confidence": 82,
                "confidence_level": "High",
                "uncertainty_ratio": 0.08,
                "uncertainty_mode": "calibrated",
                "uncertainty_reasons": [],
                "signal_breakdown": {},
            }),
            patch.object(valuation_service.response_builder, "build", return_value={
                "estimated_price": 450000,
                "price_per_m2": 3750,
                "prediction_mode": "catboost_by_type",
                "warnings": [],
                "lower_bound": 440000,
                "upper_bound": 460000,
                "confidence": 82,
                "confidence_level": "High",
                "features_impact": shap_result["features_impact"],
                "scenarios": scenario_rows,
                "recommendations": recommendation_rows,
            }),
        ):
            result = valuation_service.estimate(payload, [])

        self.assertEqual(result["features_impact"][0]["feature"], "Property Size")
        self.assertEqual(result["scenarios"][0]["scenario_name"], "Add sea view")
        self.assertEqual(result["recommendations"][0]["title"], "Add sea view")
        mock_shap.assert_called_once()
        mock_scenarios.assert_called_once()
