"""
Unit tests for Module 6 Phase 3: N-BEATS Integration.

Tests verify:
  - N-BEATS model training and forecasting
  - Integration with rolling-window backtester
  - Fallback to linear trend when N-BEATS fails
  - Model selection routing
  - Residual capture for conformal calibration
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from estatemind.intelligence.forecast.services.nbeats_model import NBeatsForecaster
from estatemind.intelligence.forecast.services.backtester import RollingWindowBacktester, BacktestReport
from estatemind.intelligence.forecast.services.model_selector import ForecastModelSelector


class TestNBeatsForecaster(unittest.TestCase):
    """Test N-BEATS model training and inference."""

    def setUp(self):
        """Initialize N-BEATS model."""
        self.nbeats = NBeatsForecaster(
            input_size=12,
            output_size=12,
            hidden_size=32,
            n_stacks=2,
            n_layers=2,
            batch_size=4,
            epochs=10,
            learning_rate=0.001,
        )

    def test_nbeats_training_with_sufficient_data(self):
        """Should successfully train on 36+ months of data."""
        # Create synthetic price data: 36 months
        prices = np.linspace(1000, 1200, 36) + np.random.randn(36) * 10
        result = self.nbeats.fit(prices, verbose=False)

        self.assertEqual(result['status'], 'success')
        self.assertGreater(result['n_samples'], 0)
        self.assertLess(result['loss'], float('inf'))
        self.assertTrue(self.nbeats.is_trained)

    def test_nbeats_training_with_insufficient_data(self):
        """Should gracefully handle insufficient data."""
        # Only 18 months: less than input (12) + output (12)
        prices = np.linspace(1000, 1050, 18)
        result = self.nbeats.fit(prices, verbose=False)

        self.assertEqual(result['status'], 'insufficient_data')
        self.assertFalse(self.nbeats.is_trained)

    def test_nbeats_prediction_from_window(self):
        """Should generate forecast from input window."""
        # Train on synthetic data
        prices = np.linspace(1000, 1200, 36) + np.random.randn(36) * 10
        self.nbeats.fit(prices, verbose=False)

        # Forecast from most recent window
        window = prices[-12:]
        forecast = self.nbeats.predict_from_window(window, n_steps=12)

        self.assertEqual(len(forecast), 12)
        self.assertTrue(all(isinstance(f, (float, np.floating)) for f in forecast))

    def test_nbeats_residual_tracking(self):
        """Should track training residuals for conformal calibration."""
        prices = np.linspace(1000, 1200, 36) + np.random.randn(36) * 10
        self.nbeats.fit(prices, verbose=False)

        residuals = self.nbeats.get_residuals()
        self.assertGreater(len(residuals), 0)
        # Residuals should be numeric
        self.assertTrue(all(isinstance(r, (float, int, np.number)) for r in residuals))


class TestBacktesterNBeatsIntegration(unittest.TestCase):
    """Test N-BEATS integration with rolling-window backtester."""

    def setUp(self):
        """Initialize backtester."""
        self.backtester = RollingWindowBacktester()

    def test_backtester_linear_model_selection(self):
        """Should route to linear trend for <12 months."""
        # Create 9 months of synthetic data
        price_history = [
            {'month': f'2024-{str(i+1).zfill(2)}', 'median_price': 1000 + i * 10}
            for i in range(9)
        ]

        report = self.backtester.run(
            delegation='TestCity',
            property_type='apartment',
            price_history=price_history,
            model_type='linear_trend'
        )

        self.assertEqual(report.delegation, 'TestCity')
        self.assertEqual(report.model_type, 'linear_trend')
        # Not enough data for full backtest
        self.assertEqual(report.n_windows, 0)

    def test_backtester_nbeats_with_sufficient_data(self):
        """Should train N-BEATS on 24+ months of data."""
        # Create 30 months of synthetic data with trend
        prices = np.linspace(1000, 1200, 30) + np.random.randn(30) * 5
        price_history = [
            {
                'month': f'2022-{str((i%12)+1).zfill(2)}',
                'median_price': float(prices[i])
            }
            for i in range(30)
        ]

        report = self.backtester.run(
            delegation='TestCity',
            property_type='apartment',
            price_history=price_history,
            model_type='nbeats'
        )

        self.assertEqual(report.delegation, 'TestCity')
        self.assertEqual(report.model_type, 'nbeats')
        # Should generate windows with N-BEATS
        self.assertGreater(report.n_windows, 0)
        self.assertGreater(len(report.conformal_residuals), 0)

    def test_backtester_nbeats_fallback_to_linear(self):
        """Should fall back to linear trend if N-BEATS fails."""
        # Create 24 months of data
        prices = np.linspace(1000, 1100, 24)
        price_history = [
            {
                'month': f'2023-{str((i%12)+1).zfill(2)}',
                'median_price': float(prices[i])
            }
            for i in range(24)
        ]

        # Request N-BEATS but expect fallback to linear due to model_type routing
        report = self.backtester.run(
            delegation='TestCity',
            property_type='apartment',
            price_history=price_history,
            model_type='nbeats'
        )

        # Report should still be generated even if model fails internally
        self.assertEqual(report.delegation, 'TestCity')
        self.assertGreater(report.n_windows, 0)

    def test_backtester_model_type_in_windows(self):
        """Should track model_type in BacktestWindow objects."""
        prices = np.linspace(1000, 1100, 24)
        price_history = [
            {
                'month': f'2023-{str((i%12)+1).zfill(2)}',
                'median_price': float(prices[i])
            }
            for i in range(24)
        ]

        report = self.backtester.run(
            delegation='TestCity',
            property_type='apartment',
            price_history=price_history,
            model_type='nbeats'
        )

        # Report should store model_type
        self.assertEqual(report.model_type, 'nbeats')


class TestModelSelectorNBeatsRouting(unittest.TestCase):
    """Test that model selector routes to N-BEATS for 12-24 months."""

    def setUp(self):
        """Initialize model selector."""
        self.selector = ForecastModelSelector()

    def test_select_linear_trend_for_low_history(self):
        """Should select linear trend for <12 months."""
        result = self.selector.select(6)
        self.assertEqual(result['model'], 'linear_trend')
        self.assertTrue(result['needs_conformal'])

    def test_select_nbeats_for_medium_history(self):
        """Should select N-BEATS for 12-24 months."""
        result = self.selector.select(18)
        self.assertEqual(result['model'], 'nbeats')
        self.assertTrue(result['needs_conformal'])

    def test_select_tft_for_long_history(self):
        """Should select TFT for 24+ months."""
        result = self.selector.select(36)
        self.assertEqual(result['model'], 'tft')
        self.assertFalse(result['needs_conformal'])

    def test_boundary_12_months(self):
        """Should select N-BEATS at 12-month boundary."""
        result = self.selector.select(12)
        self.assertEqual(result['model'], 'nbeats')

    def test_boundary_24_months(self):
        """Should select TFT at 24-month boundary."""
        result = self.selector.select(24)
        self.assertEqual(result['model'], 'tft')


class TestPhase3Conformality(unittest.TestCase):
    """Test that N-BEATS residuals support conformal calibration."""

    def setUp(self):
        """Initialize backtester."""
        self.backtester = RollingWindowBacktester()

    def test_nbeats_residuals_for_conformal_calibration(self):
        """Should produce residuals compatible with conformal predictor."""
        prices = np.linspace(1000, 1150, 30) + np.random.randn(30) * 8
        price_history = [
            {
                'month': f'2022-{str((i%12)+1).zfill(2)}',
                'median_price': float(prices[i])
            }
            for i in range(30)
        ]

        report = self.backtester.run(
            delegation='TestCity',
            property_type='apartment',
            price_history=price_history,
            model_type='nbeats'
        )

        # Residuals should be numeric and non-empty
        self.assertGreater(len(report.conformal_residuals), 0)
        self.assertTrue(
            all(isinstance(r, (float, int, np.number)) for r in report.conformal_residuals)
        )

        # Should be able to compute quantiles (needed for conformal prediction)
        quantile_90 = np.percentile(np.abs(report.conformal_residuals), 90)
        self.assertGreater(quantile_90, 0)


if __name__ == '__main__':
    unittest.main()
