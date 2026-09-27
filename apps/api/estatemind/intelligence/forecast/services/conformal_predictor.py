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
        self._quantile = None  # learned from calibration set (all horizons pooled)
        self._n_calibration = 0
        # Error grows with the forecast horizon: one pooled width over-covers
        # month 1 and under-covers month 12, so each horizon gets its own.
        self._horizon_quantiles: dict[int, float] = {}

    MIN_PER_HORIZON = 20

    def _quantile_of(self, abs_residuals: np.ndarray) -> float:
        # Split-conformal: the k-th smallest residual, k = ceil((n+1) * coverage) (1-based).
        n = len(abs_residuals)
        k = int(np.ceil((n + 1) * self.coverage))
        return float(np.sort(abs_residuals)[min(k, n) - 1])

    def calibrate(self, calibration_residuals: list, horizons: list | None = None) -> dict:
        """
        Fits the conformal predictor on historical residuals from backtesting.

        Args:
            calibration_residuals: list of (actual - predicted) values
            horizons: forecast horizon (1..12) of each residual, if known; horizons
                with at least MIN_PER_HORIZON residuals get their own quantile

        Returns a dict with calibration metadata.
        """
        residuals = np.abs(np.array(calibration_residuals, dtype=float))

        if len(residuals) < 5:
            logger.warning(
                "Insufficient calibration samples (%d < 5). Conformal predictor may be unreliable.",
                len(residuals),
            )

        n = len(residuals)
        self._quantile = self._quantile_of(residuals)
        self._n_calibration = n
        self._horizon_quantiles = {}
        if horizons is not None:
            hz = np.asarray(horizons)
            for h in np.unique(hz):
                part = residuals[hz == h]
                if len(part) >= self.MIN_PER_HORIZON:
                    self._horizon_quantiles[int(h)] = self._quantile_of(part)

        return {
            "quantile": round(self._quantile, 2),
            "coverage": self.coverage,
            "calibration_samples": n,
            "residual_p50": round(float(np.median(residuals)), 2),
            "residual_p90": round(float(np.percentile(residuals, 90)), 2),
            "valid": n >= 30,  # need at least 30 for strong reliability
            "per_horizon": bool(self._horizon_quantiles),
        }

    def quantile_for(self, horizon: int | None = None) -> float:
        return self._horizon_quantiles.get(horizon, self._quantile) if horizon else self._quantile

    def predict_interval(self, point_forecast: float, horizon: int | None = None) -> dict:
        """
        Wraps a point forecast with a coverage-guaranteed interval.

        Args:
            point_forecast: the model's point estimate
            horizon: months ahead (1..12); uses that horizon's width when calibrated

        Returns a dict with [low, high] interval and metadata.
        """
        if self._quantile is None:
            raise RuntimeError(
                "Conformal predictor must be calibrated before predicting."
            )

        q = self.quantile_for(horizon)
        low = point_forecast - q
        high = point_forecast + q
        width_pct = (q * 2) / point_forecast * 100 if point_forecast > 0 else 0

        return {
            "point": round(point_forecast, 2),
            "low": round(max(low, 0), 2),  # price cannot be negative
            "high": round(high, 2),
            "quantile": round(q, 2),
            "horizon": horizon,
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
