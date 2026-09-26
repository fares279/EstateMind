"""
Unit tests for Phase 2 — Conformal Prediction for Uncertainty Quantification.
"""

from django.test import TestCase
from django.core.cache import cache
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from estatemind.intelligence.forecast.services.conformal_calibration import ConformalCalibratorOrchestrator
from estatemind.intelligence.forecast.services.conformal_predictor import ConformalPredictor


class TestConformalCalibratorOrchestrator(TestCase):
    """Tests for conformal calibration orchestration."""

    def setUp(self):
        # Clear cache before each test
        cache.clear()
        self.orchestrator = ConformalCalibratorOrchestrator(coverage=0.90)

    @patch('estatemind.intelligence.forecast.models.ForecastModelVersion')
    def test_get_or_calibrate_predictor_with_residuals(self, mock_model_version_class):
        """Should calibrate predictor when residuals are available."""
        # Mock model version with residuals
        mock_instance = MagicMock()
        mock_instance.conformal_residuals = np.random.normal(0, 50, 50).tolist()
        mock_model_version_class.objects.filter.return_value.order_by.return_value.first.return_value = (
            mock_instance
        )

        result = self.orchestrator.get_or_calibrate_predictor("Tunis", "apartment")

        self.assertIsNotNone(result)
        predictor, metadata = result
        self.assertIsInstance(predictor, ConformalPredictor)
        self.assertGreater(metadata.get("quantile"), 0)
        self.assertEqual(metadata.get("coverage"), 0.90)

    @patch('estatemind.intelligence.forecast.models.ForecastModelVersion')
    def test_get_or_calibrate_predictor_without_residuals(self, mock_model_version_class):
        """Should return None when no residuals available."""
        mock_model_version_class.objects.filter.return_value.order_by.return_value.first.return_value = None

        result = self.orchestrator.get_or_calibrate_predictor("NonExistent", "apartment")

        self.assertIsNone(result)

    @patch('estatemind.intelligence.forecast.models.ForecastModelVersion')
    def test_predict_with_intervals(self, mock_model_version_class):
        """Should wrap point forecast with calibrated intervals."""
        mock_instance = MagicMock()
        mock_instance.conformal_residuals = np.random.normal(0, 50, 50).tolist()
        mock_model_version_class.objects.filter.return_value.order_by.return_value.first.return_value = (
            mock_instance
        )

        interval = self.orchestrator.predict_with_intervals("TestDel", "villa", 2000.0)

        self.assertIsNotNone(interval)
        self.assertEqual(interval["point"], 2000.0)
        self.assertLess(interval["low"], 2000.0)
        self.assertGreater(interval["high"], 2000.0)
        self.assertEqual(interval["coverage"], 0.90)

    @patch('estatemind.intelligence.forecast.models.ForecastModelVersion')
    def test_predict_quantile_fan(self, mock_model_version_class):
        """Should produce nested confidence intervals for fan chart."""
        mock_instance = MagicMock()
        mock_instance.conformal_residuals = np.random.normal(0, 50, 50).tolist()
        mock_model_version_class.objects.filter.return_value.order_by.return_value.first.return_value = (
            mock_instance
        )

        fan = self.orchestrator.predict_quantile_fan(
            "TestDel2", "land", 2000.0, levels=[0.50, 0.70, 0.80, 0.90]
        )

        self.assertIsNotNone(fan)
        self.assertEqual(len(fan), 4)
        # Widths should increase with coverage level
        widths = [item["high"] - item["low"] for item in fan]
        self.assertEqual(widths, sorted(widths))

    @patch('estatemind.intelligence.forecast.models.ForecastModelVersion')
    def test_get_calibration_metadata(self, mock_model_version_class):
        """Should return calibration metadata without full predictor."""
        mock_instance = MagicMock()
        mock_instance.conformal_residuals = np.random.normal(0, 50, 50).tolist()
        mock_model_version_class.objects.filter.return_value.order_by.return_value.first.return_value = (
            mock_instance
        )

        metadata = self.orchestrator.get_calibration_metadata("TestDel3", "apartment")

        self.assertIsNotNone(metadata)
        self.assertIn("quantile", metadata)
        self.assertIn("coverage", metadata)
        self.assertIn("calibration_samples", metadata)
        self.assertIn("residual_p50", metadata)
        self.assertIn("residual_p90", metadata)
        self.assertIn("valid", metadata)


class TestPhase2Fallback(TestCase):
    """Tests for fallback behavior when conformal is unavailable."""

    def setUp(self):
        cache.clear()

    @patch('estatemind.intelligence.forecast.models.ForecastModelVersion')
    def test_fallback_to_fixed_mape_when_no_residuals(self, mock_model_version_class):
        """Should fall back to fixed MAPE when conformal residuals unavailable."""
        mock_model_version_class.objects.filter.return_value.order_by.return_value.first.return_value = None

        orchestrator = ConformalCalibratorOrchestrator()
        
        # Should return None and fallback gracefully
        result = orchestrator.get_or_calibrate_predictor("NoResiduals", "apartment")
        self.assertIsNone(result)
