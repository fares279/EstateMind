from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from estatemind.intelligence.valuation.inference.request_mapper import map_request
from estatemind.intelligence.valuation.services import valuation_service
from estatemind.intelligence.valuation.services.counterfactual_engine import CounterfactualEngine
from estatemind.intelligence.valuation.services.response_builder import build as build_response


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


class ValuationGovernanceTests(SimpleTestCase):
    def test_response_builder_includes_provenance_and_counterfactuals(self):
        model_version = SimpleNamespace(
            model_name='CatBoost_Apartment',
            version='1.0',
            training_date=__import__('datetime').date(2026, 5, 1),
            eval_rmse=1200.0,
            eval_r2=0.93,
            eval_mape=7.5,
            artifact_path='backend/valuation/artifacts/valuation_model.joblib',
        )
        response = build_response(
            _payload(),
            {'estimated_price': 450000, 'price_per_m2': 3750, 'prediction_mode': 'catboost_by_type', 'warnings': []},
            {'confidence': 82, 'confidence_level': 'High', 'lower_bound': 440000, 'upper_bound': 460000, 'uncertainty_ratio': 0.08, 'uncertainty_mode': 'calibrated', 'uncertainty_reasons': [], 'signal_breakdown': {}},
            {'features_impact': [{'feature': 'Location', 'impact': 50000, 'direction': 'positive', 'percent': 11.1}], 'shap': {'baseline': 300000, 'contributions': [], 'predicted': 450000}},
            [],
            {'avg_price_per_m2': 3750, 'comparable_count': 2},
            {'sentiment_mode': 'neutral'},
            'The property is valued close to market.',
            model_version=model_version,
            snapshot_date=__import__('datetime').date(2026, 5, 15),
            property_image_result={'available': True, 'condition_score': 78, 'image_confidence': 0.81, 'images_used': 3, 'images_rejected': 1},
            counterfactuals=[{'feature': 'condition', 'delta_tnd': 25000}],
        )

        self.assertEqual(response['model_name'], 'CatBoost_Apartment')
        self.assertEqual(response['provenance']['data_vintage'], '2026-05-15')
        self.assertTrue(response['image_contribution']['available'])
        self.assertEqual(response['counterfactuals'][0]['feature'], 'condition')
        self.assertEqual(response['top_drivers'][0]['feature'], 'Location')

    def test_counterfactual_engine_generates_candidate(self):
        engine = CounterfactualEngine()
        result = engine.generate(
            object(),
            {'size_m2': 120, 'condition': 1.0, 'bedrooms': 2, 'bathrooms': 1},
            400000,
            predict_fn=lambda features: 400000 * (float(features.get('size_m2', 120)) / 120.0),
        )

        self.assertTrue(result)
        self.assertIn('description', result[0])
