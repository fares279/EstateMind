"""
Unit tests for Module 6 forecast services.
"""

from django.test import TestCase
import numpy as np

from estatemind.intelligence.forecast.services.backtester import RollingWindowBacktester
from estatemind.intelligence.forecast.services.model_selector import ForecastModelSelector, ForecastModel
from estatemind.intelligence.forecast.services.conformal_predictor import ConformalPredictor
from estatemind.intelligence.forecast.services.retraining_trigger import ForecastRetrainingTrigger


class TestRollingWindowBacktester(TestCase):
    """Tests for backtesting logic."""

    def setUp(self):
        self.backtester = RollingWindowBacktester()

    def test_insufficient_data(self):
        """Backtest with < MIN_TRAIN_MONTHS + FORECAST_HORIZON should return qualified=False."""
        short_history = [
            {"month": "2024-01", "median_price": 1000},
            {"month": "2024-02", "median_price": 1100},
        ]
        result = self.backtester.run("test_delegation", "apartment", short_history)
        self.assertFalse(result.model_qualified)
        self.assertEqual(result.n_windows, 0)

    def test_linear_trend_backtest(self):
        """Backtest on linear trend should produce reasonable MAPE."""
        # Create a perfect linear trend: y = 1000 + 10*t
        history = [
            {"month": f"2023-{i:02d}", "median_price": 1000 + 10 * i}
            for i in range(36)  # 36 months = 3 years
        ]

        result = self.backtester.run("test_delegation", "apartment", history)

        # Linear model should fit linear data well (MAPE < 10%)
        self.assertGreater(result.n_windows, 0)
        self.assertLess(result.median_mape, 10.0)
        self.assertIsInstance(result.conformal_residuals, list)

    def test_regime_shift_detection(self):
        """Backtest should detect regime shifts when MAPE spikes."""
        # Stable trend for 24 months
        history = [
            {"month": f"2023-{i:02d}", "median_price": 1000 + 5 * i}
            for i in range(24)
        ]
        # Add a sudden shift (regime change)
        history.extend(
            [
                {"month": f"2024-{i:02d}", "median_price": 2000 + 100 * i}
                for i in range(12)
            ]
        )

        result = self.backtester.run("test_delegation", "apartment", history)

        # Should detect at least one regime shift window
        # (where MAPE spiked > 2x median)
        self.assertGreater(len(result.regime_shift_windows), 0)


class TestForecastModelSelector(TestCase):
    """Tests for model selection logic."""

    def setUp(self):
        self.selector = ForecastModelSelector()

    def test_select_linear_for_short_history(self):
        """< 12 months should select LINEAR_TREND."""
        result = self.selector.select(6)
        self.assertEqual(result["model"], "linear_trend")
        self.assertTrue(result["needs_conformal"])

    def test_select_nbeats_for_medium_history(self):
        """12–24 months should select NBEATS."""
        result = self.selector.select(18)
        self.assertEqual(result["model"], "nbeats")
        self.assertTrue(result["needs_conformal"])

    def test_select_tft_for_long_history(self):
        """≥ 24 months should select TFT."""
        result = self.selector.select(36)
        self.assertEqual(result["model"], "tft")
        self.assertFalse(result["needs_conformal"])

    def test_reason_generation(self):
        """Each model choice should have a clear reason."""
        for months in [6, 18, 36]:
            result = self.selector.select(months)
            self.assertIn("reason", result)
            self.assertGreater(len(result["reason"]), 0)


class TestConformalPredictor(TestCase):
    """Tests for conformal prediction intervals."""

    def setUp(self):
        self.predictor = ConformalPredictor(coverage=0.90)

    def test_calibration(self):
        """Calibration should learn the empirical quantile."""
        residuals = np.random.normal(0, 50, 50).tolist()
        result = self.predictor.calibrate(residuals)

        self.assertIsNotNone(self.predictor._quantile)
        self.assertGreater(self.predictor._quantile, 0)
        self.assertEqual(result["coverage"], 0.90)

    def test_prediction_interval(self):
        """Prediction interval should wrap point forecast with quantile."""
        residuals = np.random.normal(0, 50, 50).tolist()
        self.predictor.calibrate(residuals)

        point_forecast = 2000.0
        interval = self.predictor.predict_interval(point_forecast)

        self.assertEqual(interval["point"], 2000.0)
        self.assertLess(interval["low"], point_forecast)
        self.assertGreater(interval["high"], point_forecast)
        self.assertEqual(interval["coverage"], 0.90)

    def test_quantile_fan(self):
        """Quantile fan should produce nested confidence intervals."""
        residuals = np.random.normal(0, 50, 50).tolist()
        self.predictor.calibrate(residuals)

        fan = self.predictor.predict_quantile_fan(2000.0)

        # Should have 4 levels by default
        self.assertEqual(len(fan), 4)

        # Widths should be increasing
        widths = [item["high"] - item["low"] for item in fan]
        self.assertEqual(widths, sorted(widths))  # strictly increasing


class TestForecastRetrainingTrigger(TestCase):
    """Tests for retraining trigger logic."""

    def setUp(self):
        self.trigger = ForecastRetrainingTrigger()

    def test_insufficient_data(self):
        """Trigger should not fire with < MIN_SAMPLE_SIZE."""
        result = self.trigger.check(
            "test_delegation",
            "apartment",
            [1000, 1100],
            [1200, 1300],
        )
        self.assertFalse(result["should_retrain"])
        self.assertEqual(result["reason"], "insufficient_data")

    def test_stable_distribution(self):
        """Trigger should not fire when distributions are the same."""
        # Same distribution repeated twice
        prices = np.random.normal(2000, 200, 30).tolist()
        result = self.trigger.check(
            "test_delegation",
            "apartment",
            prices,
            prices,
        )
        # p-value should be high (distributions are identical)
        self.assertGreater(result["p_value"], 0.05)
        self.assertFalse(result["should_retrain"])

    def test_shifted_distribution(self):
        """Trigger should fire when distributions are significantly different."""
        training_prices = np.random.normal(1500, 100, 30).tolist()
        recent_prices = np.random.normal(2500, 100, 30).tolist()

        result = self.trigger.check(
            "test_delegation",
            "apartment",
            training_prices,
            recent_prices,
        )
        # Distributions are very different, so p-value should be small
        self.assertLess(result["p_value"], 0.05)
        self.assertTrue(result["should_retrain"])
