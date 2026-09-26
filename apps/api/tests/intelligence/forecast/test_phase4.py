"""
Unit tests for Module 6 Phase 4: TFT (Temporal Fusion Transformer) Integration.

Tests verify:
  - TFT model training and native quantile prediction
  - Integration with rolling-window backtester
  - Fallback to linear trend when TFT fails
  - Model selection routing for 24+ month delegations
  - Native quantile outputs (no conformal wrapper needed)
"""

import unittest
from unittest.mock import Mock, patch
import numpy as np

from estatemind.intelligence.forecast.services.tft_model import TFTForecaster
from estatemind.intelligence.forecast.services.backtester import RollingWindowBacktester
from estatemind.intelligence.forecast.services.model_selector import ForecastModelSelector


class TestTFTForecaster(unittest.TestCase):
    """Test TFT model training and inference."""

    def setUp(self):
        """Initialize TFT model."""
        self.tft = TFTForecaster(
            input_size=24,
            output_size=12,
            hidden_size=32,
            n_layers=2,
            n_heads=4,
            n_quantiles=5,
            batch_size=4,
            epochs=10,
            learning_rate=0.001,
        )

    def test_tft_training_with_sufficient_data(self):
        """Should successfully train on 48+ months of data."""
        # Create synthetic price data: 48 months
        prices = np.linspace(1000, 1400, 48) + np.random.randn(48) * 15
        result = self.tft.fit(prices, verbose=False)

        self.assertEqual(result['status'], 'success')
        self.assertGreater(result['n_samples'], 0)
        self.assertLess(result['loss'], float('inf'))
        self.assertTrue(self.tft.is_trained)

    def test_tft_training_with_insufficient_data(self):
        """Should gracefully handle insufficient data."""
        # Only 30 months: less than input (24) + output (12)
        prices = np.linspace(1000, 1050, 30)
        result = self.tft.fit(prices, verbose=False)

        self.assertEqual(result['status'], 'insufficient_data')
        self.assertFalse(self.tft.is_trained)

    def test_tft_native_quantile_prediction(self):
        """Should generate native quantile forecasts."""
        # Train on synthetic data
        prices = np.linspace(1000, 1400, 48) + np.random.randn(48) * 15
        self.tft.fit(prices, verbose=False)

        # Predict from most recent window
        window = prices[-24:]
        forecast_dict = self.tft.predict_from_window(window, n_steps=12)

        # Should have quantiles, point, lower, upper
        self.assertIn('quantiles', forecast_dict)
        self.assertIn('point', forecast_dict)
        self.assertIn('lower', forecast_dict)
        self.assertIn('upper', forecast_dict)

        # Point forecast should have 12 values
        self.assertEqual(len(forecast_dict['point']), 12)

        # Quantiles should include all 5 levels
        self.assertEqual(len(forecast_dict['quantiles']), 5)

    def test_tft_quantile_levels_exist(self):
        """Should produce all quantile levels in output."""
        prices = np.linspace(1000, 1400, 48) + np.random.randn(48) * 15
        self.tft.fit(prices, verbose=False)

        window = prices[-24:]
        forecast_dict = self.tft.predict_from_window(window, n_steps=12)

        # All quantile levels should be present
        for q_level in [0.1, 0.3, 0.5, 0.7, 0.9]:
            self.assertIn(q_level, forecast_dict['quantiles'])

    def test_tft_quantile_bounds_exist(self):
        """Should provide lower and upper bounds (q0.1 and q0.9)."""
        prices = np.linspace(1000, 1400, 48) + np.random.randn(48) * 15
        self.tft.fit(prices, verbose=False)

        window = prices[-24:]
        forecast_dict = self.tft.predict_from_window(window, n_steps=12)

        # Bounds should exist and be numeric
        self.assertIn('lower', forecast_dict)
        self.assertIn('upper', forecast_dict)
        self.assertTrue(all(isinstance(x, (float, int)) for x in forecast_dict['lower']))
        self.assertTrue(all(isinstance(x, (float, int)) for x in forecast_dict['upper']))

    def test_tft_residual_tracking(self):
        """Should track training residuals for backward compatibility."""
        prices = np.linspace(1000, 1400, 48) + np.random.randn(48) * 15
        self.tft.fit(prices, verbose=False)

        residuals = self.tft.get_residuals()
        self.assertGreater(len(residuals), 0)


class TestBacktesterTFTIntegration(unittest.TestCase):
    """Test TFT integration with rolling-window backtester."""

    def setUp(self):
        """Initialize backtester."""
        self.backtester = RollingWindowBacktester()

    def test_backtester_tft_with_sufficient_data(self):
        """Should train TFT on 48+ months of data."""
        # Create 60 months of synthetic data
        prices = np.linspace(1000, 1500, 60) + np.random.randn(60) * 10
        price_history = [
            {
                'month': f'2020-{str((i%12)+1).zfill(2)}',
                'median_price': float(prices[i])
            }
            for i in range(60)
        ]

        report = self.backtester.run(
            delegation='TestCity',
            property_type='apartment',
            price_history=price_history,
            model_type='tft'
        )

        self.assertEqual(report.delegation, 'TestCity')
        self.assertEqual(report.model_type, 'tft')
        # Should generate windows with TFT
        self.assertGreater(report.n_windows, 0)
        self.assertGreater(len(report.conformal_residuals), 0)

    def test_backtester_tft_fallback_to_linear(self):
        """Should fall back to linear trend if TFT training fails."""
        # Create only 36 months (might be insufficient for early windows)
        prices = np.linspace(1000, 1150, 36)
        price_history = [
            {
                'month': f'2023-{str((i%12)+1).zfill(2)}',
                'median_price': float(prices[i])
            }
            for i in range(36)
        ]

        report = self.backtester.run(
            delegation='TestCity',
            property_type='apartment',
            price_history=price_history,
            model_type='tft'
        )

        # Report should still be generated
        self.assertEqual(report.delegation, 'TestCity')
        self.assertGreater(report.n_windows, 0)

    def test_backtester_model_type_field_tft(self):
        """Should track model_type as 'tft' in BacktestReport."""
        prices = np.linspace(1000, 1300, 48)
        price_history = [
            {
                'month': f'2022-{str((i%12)+1).zfill(2)}',
                'median_price': float(prices[i])
            }
            for i in range(48)
        ]

        report = self.backtester.run(
            delegation='TestCity',
            property_type='apartment',
            price_history=price_history,
            model_type='tft'
        )

        self.assertEqual(report.model_type, 'tft')


class TestModelSelectorTFTRouting(unittest.TestCase):
    """Test that model selector correctly routes to TFT."""

    def setUp(self):
        """Initialize model selector."""
        self.selector = ForecastModelSelector()

    def test_select_tft_for_24_plus_months(self):
        """Should select TFT for 24+ months."""
        result = self.selector.select(24)
        self.assertEqual(result['model'], 'tft')
        self.assertFalse(result['needs_conformal'])

    def test_select_tft_for_48_months(self):
        """Should select TFT for 48 months."""
        result = self.selector.select(48)
        self.assertEqual(result['model'], 'tft')

    def test_select_tft_for_60_months(self):
        """Should select TFT for very long history."""
        result = self.selector.select(60)
        self.assertEqual(result['model'], 'tft')

    def test_tft_does_not_need_conformal(self):
        """TFT should not need conformal wrapper (native quantiles)."""
        result = self.selector.select(36)
        self.assertFalse(result['needs_conformal'])
        # Linear and N-BEATS need conformal
        self.assertTrue(self.selector.select(6)['needs_conformal'])
        self.assertTrue(self.selector.select(18)['needs_conformal'])


class TestPhase4NativeQuantiles(unittest.TestCase):
    """Test that TFT produces native quantile predictions."""

    def setUp(self):
        """Initialize backtester."""
        self.backtester = RollingWindowBacktester()

    def test_tft_produces_residuals_for_backward_compatibility(self):
        """TFT should produce residuals even though it has native quantiles."""
        prices = np.linspace(1000, 1500, 60) + np.random.randn(60) * 10
        price_history = [
            {
                'month': f'2020-{str((i%12)+1).zfill(2)}',
                'median_price': float(prices[i])
            }
            for i in range(60)
        ]

        report = self.backtester.run(
            delegation='TestCity',
            property_type='apartment',
            price_history=price_history,
            model_type='tft'
        )

        # TFT should still produce residuals for consistency
        self.assertGreater(len(report.conformal_residuals), 0)
        self.assertTrue(
            all(isinstance(r, (float, int, np.number)) for r in report.conformal_residuals)
        )


class TestPhase4ModelSplitByHistory(unittest.TestCase):
    """Test complete model routing pipeline (Phase 1-4)."""

    def setUp(self):
        """Initialize selector and backtester."""
        self.selector = ForecastModelSelector()
        self.backtester = RollingWindowBacktester()

    def test_routing_pipeline_short_history(self):
        """<12 months should route to linear trend."""
        result = self.selector.select(6)
        self.assertEqual(result['model'], 'linear_trend')

    def test_routing_pipeline_medium_history(self):
        """12-24 months should route to N-BEATS."""
        result = self.selector.select(18)
        self.assertEqual(result['model'], 'nbeats')

    def test_routing_pipeline_long_history(self):
        """24+ months should route to TFT."""
        result = self.selector.select(36)
        self.assertEqual(result['model'], 'tft')

    def test_backtesting_all_models_produce_mape(self):
        """All three models should produce MAPE metrics."""
        prices = np.linspace(1000, 1500, 60)
        price_history = [
            {
                'month': f'2020-{str((i%12)+1).zfill(2)}',
                'median_price': float(prices[i])
            }
            for i in range(60)
        ]

        # Test each model
        for model_type in ['linear_trend', 'nbeats', 'tft']:
            with self.subTest(model_type=model_type):
                report = self.backtester.run(
                    delegation='TestCity',
                    property_type='apartment',
                    price_history=price_history,
                    model_type=model_type,
                )

                self.assertEqual(report.model_type, model_type)
                # All should generate windows (60 months is sufficient for all)
                self.assertGreater(report.n_windows, 0)
                # MAPE should be produced
                self.assertGreaterEqual(report.median_mape, 0)


if __name__ == '__main__':
    unittest.main()
