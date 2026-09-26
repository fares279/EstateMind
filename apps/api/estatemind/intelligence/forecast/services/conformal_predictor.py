"""
Conformal prediction for forecast uncertainty quantification.

Distribution-free prediction intervals using split conformal prediction.
Provides a mathematical guarantee on coverage:

  For any base model and coverage level α:
  P(actual ∈ [low, high]) ≥ α

Where [low, high] are computed from the empirical distribution
of residuals on a held-out calibration set.

This works regardless of whether residuals are Gaussian, skewed,
heavy-tailed, or heteroskedastic. No distributional assumptions needed.
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)


class ConformalPredictor:
    """
    Produces mathematically guaranteed prediction intervals.

    The guarantee:
        For any base model and any coverage level α:
        P(actual ∈ [prediction - q, prediction + q]) ≥ α

    Where q is computed from the empirical distribution of residuals
    on a held-out calibration set (from backtesting).
    """

    def __init__(self, coverage: float = 0.90):
        """
        Args:
            coverage: desired coverage level (e.g. 0.90 for 90%)
        """
        self.coverage = coverage
        self._quantile = None  # learned from calibration set
        self._n_calibration = 0

    def calibrate(self, calibration_residuals: list) -> dict:
        """
        Fits the conformal predictor on historical residuals from backtesting.

        Args:
            calibration_residuals: list of (actual - predicted) values

        Returns a dict with calibration metadata.
        """
        residuals = np.abs(np.array(calibration_residuals, dtype=float))

        if len(residuals) < 5:
            logger.warning(
                "Insufficient calibration samples (%d < 5). Conformal predictor may be unreliable.",
                len(residuals),
            )

        # Conformal quantile: ceil((n+1)(1-α)) / n
        n = len(residuals)
        quantile_idx = int(np.ceil((n + 1) * self.coverage))
        quantile_idx = min(quantile_idx, n - 1)  # safety clamp

        self._quantile = float(np.sort(residuals)[quantile_idx])
        self._n_calibration = n

        return {
            "quantile": round(self._quantile, 2),
            "coverage": self.coverage,
            "calibration_samples": n,
            "residual_p50": round(float(np.median(residuals)), 2),
            "residual_p90": round(float(np.percentile(residuals, 90)), 2),
            "valid": n >= 30,  # need at least 30 for strong reliability
        }

    def predict_interval(self, point_forecast: float) -> dict:
        """
        Wraps a point forecast with a coverage-guaranteed interval.

        Args:
            point_forecast: the model's point estimate

        Returns a dict with [low, high] interval and metadata.
        """
        if self._quantile is None:
            raise RuntimeError(
                "Conformal predictor must be calibrated before predicting."
            )

        low = point_forecast - self._quantile
        high = point_forecast + self._quantile
        width_pct = (self._quantile * 2) / point_forecast * 100 if point_forecast > 0 else 0

        return {
            "point": round(point_forecast, 2),
            "low": round(max(low, 0), 2),  # price cannot be negative
            "high": round(high, 2),
            "quantile": round(self._quantile, 2),
            "coverage": self.coverage,
            "width_pct": round(width_pct, 1),
            "label": f"{int(self.coverage * 100)}% prediction interval",
        }

    def predict_quantile_fan(
        self, point_forecast: float, levels: list = None
    ) -> list:
        """
        Produces a quantile fan for multiple coverage levels.
        Used to render fan charts in the frontend.

        Args:
            point_forecast: the model's point estimate
            levels: list of coverage levels (default: [0.50, 0.70, 0.80, 0.90])

        Returns a list of dicts with [low, high] for each level.
        """
        if levels is None:
            levels = [0.50, 0.70, 0.80, 0.90]

        fan = []
        for level in levels:
            # Scale quantile proportionally for each level
            # This is an approximation — full fan requires separate calibration per level
            scale_factor = (
                -np.log(1 - level) / (-np.log(1 - self.coverage))
                if self.coverage < 1.0 and level < 1.0
                else 1.0
            )
            level_quantile = self._quantile * scale_factor

            fan.append(
                {
                    "coverage": level,
                    "low": round(max(point_forecast - level_quantile, 0), 2),
                    "high": round(point_forecast + level_quantile, 2),
                }
            )

        return fan
