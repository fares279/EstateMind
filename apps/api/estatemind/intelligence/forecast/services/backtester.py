"""
Rolling-window backtesting for forecast models.

The backtester validates whether a model generalizes to unseen data
by repeatedly splitting the historical record into training and testing
windows, advancing the window forward in time, and measuring forecast error
at each step. The result is a MAPE time series showing the model's
real-world accuracy over different market regimes.
"""

import logging
import numpy as np
from dataclasses import dataclass
from typing import List, Optional

from estatemind.intelligence.forecast.services.nbeats_model import NBeatsForecaster
from estatemind.intelligence.forecast.services.tft_model import TFTForecaster

logger = logging.getLogger(__name__)


@dataclass
class BacktestWindow:
    """Single rolling window result."""
    train_start: str  # "2022-01"
    train_end: str  # "2022-12"
    test_start: str  # "2023-01"
    test_end: str  # "2023-12"
    mape: float  # realized error for this window
    residuals: List[float]  # actual - predicted for each test month
    model_type: str = 'linear_trend'  # 'linear_trend' or 'nbeats'


@dataclass
class BacktestReport:
    """Complete backtest result for a delegation × property type."""
    delegation: str
    property_type: str
    n_windows: int
    median_mape: float
    p90_mape: float
    max_mape: float
    regime_shift_windows: List[int]  # windows where MAPE spiked > 2x median
    conformal_residuals: List[float]  # all residuals, used for band calibration
    model_qualified: bool  # True if median MAPE < MAPE_THRESHOLD
    model_type: str = 'linear_trend'  # 'linear_trend' or 'nbeats'


class RollingWindowBacktester:
    """
    Validates a forecasting model by simulating how it would have
    performed at every point in the historical record.

    MAPE < 10%: strong model — qualified for production
    MAPE 10–15%: acceptable — serve with wider confidence band
    MAPE > 15%: poor — fallback to simpler model or flag uncertainty
    """

    MAPE_THRESHOLD = 10.0  # % — median MAPE below this = qualified
    MIN_TRAIN_MONTHS = 12  # minimum history to train on
    FORECAST_HORIZON = 12  # how many months to forecast per window
    REGIME_MULTIPLIER = 2.0  # MAPE spike above 2x median = regime shift

    def run(
        self, delegation: str, property_type: str, price_history: List[dict],
        model_type: str = 'linear_trend'
    ) -> BacktestReport:
        """
        price_history: list of {'month': 'YYYY-MM', 'median_price': float}
        sorted chronologically.
        model_type: 'linear_trend' or 'nbeats'

        Returns a BacktestReport with MAPE trajectory and regime detection.
        """
        if len(price_history) < self.MIN_TRAIN_MONTHS + self.FORECAST_HORIZON:
            return self._insufficient_data_report(delegation, property_type)

        windows = []
        all_residuals = []
        n = len(price_history)

        for t in range(self.MIN_TRAIN_MONTHS, n - self.FORECAST_HORIZON + 1):
            train_data = price_history[:t]
            test_data = price_history[t : t + self.FORECAST_HORIZON]

            train_prices = [d.get("median_price", d.get("price")) for d in train_data]
            test_prices = [d.get("median_price", d.get("price")) for d in test_data]

            # Fit model and forecast for this window
            forecast = self._fit_and_forecast(
                train_prices, self.FORECAST_HORIZON, model_type=model_type
            )

            # Compute residuals and MAPE
            residuals = [actual - pred for actual, pred in zip(test_prices, forecast)]
            mape = np.mean(
                [
                    abs(actual - pred) / actual * 100
                    for actual, pred in zip(test_prices, forecast)
                    if actual > 0
                ]
            )

            train_start = train_data[0].get("month", "unknown")
            train_end = train_data[-1].get("month", "unknown")
            test_start = test_data[0].get("month", "unknown")
            test_end = test_data[-1].get("month", "unknown")

            windows.append(
                BacktestWindow(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    mape=round(float(mape), 2),
                    residuals=residuals,
                    model_type=model_type,
                )
            )
            all_residuals.extend(residuals)

        mape_values = [w.mape for w in windows]
        median_mape = float(np.median(mape_values))
        p90_mape = float(np.percentile(mape_values, 90))
        max_mape = float(np.max(mape_values))

        # Detect regime shifts: windows where MAPE > 2x median
        regime_shifts = [
            i
            for i, w in enumerate(windows)
            if w.mape > median_mape * self.REGIME_MULTIPLIER
        ]

        return BacktestReport(
            delegation=delegation,
            property_type=property_type,
            n_windows=len(windows),
            median_mape=round(median_mape, 2),
            p90_mape=round(p90_mape, 2),
            max_mape=round(max_mape, 2),
            regime_shift_windows=regime_shifts,
            conformal_residuals=all_residuals,
            model_qualified=median_mape < self.MAPE_THRESHOLD,
            model_type=model_type,
        )

    def _fit_and_forecast(
        self, train_prices: List[float], horizon: int, model_type: str = 'linear_trend'
    ) -> List[float]:
        """
        Fits a model and forecasts forward.
        Routes to model-specific implementation based on model_type.

        Args:
            train_prices: Historical price sequence
            horizon: Number of periods to forecast
            model_type: 'linear_trend', 'nbeats', or 'tft'

        Returns:
            List of point forecasts for the next `horizon` periods.
        """
        if model_type == 'nbeats':
            return self._fit_and_forecast_nbeats(train_prices, horizon)
        elif model_type == 'tft':
            return self._fit_and_forecast_tft(train_prices, horizon)
        else:
            # Default to linear trend
            return self._fit_and_forecast_linear(train_prices, horizon)

    def _fit_and_forecast_linear(
        self, train_prices: List[float], horizon: int
    ) -> List[float]:
        """
        Fits a simple linear trend model and forecasts forward.
        Returns a list of point forecasts for the next `horizon` periods.
        """
        if len(train_prices) < 2:
            return [train_prices[-1]] * horizon

        x = np.arange(len(train_prices), dtype=float)
        y = np.array(train_prices, dtype=float)

        # Fit linear trend: y = a + b*t
        coeffs = np.polyfit(x, y, 1)
        a, b = coeffs[0], coeffs[1]

        # Forecast
        forecast_x = np.arange(len(train_prices), len(train_prices) + horizon)
        forecast = a * forecast_x + b

        return forecast.tolist()

    def _fit_and_forecast_nbeats(
        self, train_prices: List[float], horizon: int
    ) -> List[float]:
        """
        Fits N-BEATS neural model and forecasts forward.
        Falls back to linear trend if N-BEATS training fails.

        Args:
            train_prices: Historical price sequence (>=24 months recommended)
            horizon: Number of periods to forecast (typically 12)

        Returns:
            List of point forecasts for the next `horizon` periods.
        """
        try:
            # Initialize N-BEATS with standard 12-month lookback
            nbeats = NBeatsForecaster(
                input_size=min(12, len(train_prices) // 2),
                output_size=horizon,
                hidden_size=64,
                n_stacks=2,
                n_layers=2,
                batch_size=4,
                epochs=50,
                learning_rate=0.001,
            )

            # Train model
            result = nbeats.fit(np.array(train_prices), verbose=False)
            if result['status'] != 'success':
                logger.warning(
                    f"N-BEATS training failed: {result['status']}. "
                    "Falling back to linear trend."
                )
                return self._fit_and_forecast_linear(train_prices, horizon)

            # Predict from most recent window
            window = np.array(train_prices[-nbeats.input_size:])
            forecast = nbeats.predict_from_window(window, n_steps=horizon)

            return forecast.tolist()

        except Exception as e:
            logger.warning(
                f"N-BEATS forecasting error: {str(e)}. "
                "Falling back to linear trend."
            )
            return self._fit_and_forecast_linear(train_prices, horizon)

    def _fit_and_forecast_tft(
        self, train_prices: List[float], horizon: int
    ) -> List[float]:
        """
        Fits TFT neural model and forecasts forward.
        Falls back to linear trend if TFT training fails.

        Args:
            train_prices: Historical price sequence (>=36 months recommended)
            horizon: Number of periods to forecast (typically 12)

        Returns:
            List of point forecasts for the next `horizon` periods.
        """
        try:
            # Initialize TFT with 24-month lookback (typical for TFT)
            tft = TFTForecaster(
                input_size=min(24, len(train_prices) // 2),
                output_size=horizon,
                hidden_size=64,
                n_layers=2,
                n_heads=4,
                n_quantiles=5,
                batch_size=4,
                epochs=50,
                learning_rate=0.001,
            )

            # Train model
            result = tft.fit(np.array(train_prices), verbose=False)
            if result['status'] != 'success':
                logger.warning(
                    f"TFT training failed: {result['status']}. "
                    "Falling back to linear trend."
                )
                return self._fit_and_forecast_linear(train_prices, horizon)

            # Predict from most recent window
            window = np.array(train_prices[-tft.input_size:])
            forecast_dict = tft.predict_from_window(window, n_steps=horizon)

            # Extract point forecast from TFT's dict output
            if 'point' in forecast_dict:
                return forecast_dict['point']
            else:
                logger.warning(
                    "TFT forecast dict missing 'point' key. Falling back to linear trend."
                )
                return self._fit_and_forecast_linear(train_prices, horizon)

        except Exception as e:
            logger.warning(
                f"TFT forecasting error: {str(e)}. "
                "Falling back to linear trend."
            )
            return self._fit_and_forecast_linear(train_prices, horizon)

    def _insufficient_data_report(
        self, delegation: str, property_type: str
    ) -> BacktestReport:
        return BacktestReport(
            delegation=delegation,
            property_type=property_type,
            n_windows=0,
            median_mape=0.0,
            p90_mape=0.0,
            max_mape=0.0,
            regime_shift_windows=[],
            conformal_residuals=[],
            model_qualified=False,
        )
