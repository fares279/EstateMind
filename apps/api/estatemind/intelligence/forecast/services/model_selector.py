"""
Model selection logic for forecast models.

Selects the appropriate forecasting model based on available history depth.
The selection is deterministic, versioned, and logged for auditability.

LINEAR_TREND: < 12 months
  Fits y = a + b*t using simple OLS
  Pros: interpretable, never overfits, works with 3+ months
  Cons: cannot capture seasonality

N-BEATS: 12–24 months
  Pure neural architecture; learns basis functions from data
  Pros: captures complex patterns without feature engineering
  Cons: requires conformal wrapping for prediction intervals

TFT: ≥ 24 months (optional: with external covariates)
  Temporal Fusion Transformer; handles covariates natively
  Pros: produces native quantile forecasts, interpretable attention
  Cons: slower to train, requires more compute
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ForecastModel(Enum):
    LINEAR_TREND = "linear_trend"
    NBEATS = "nbeats"
    TFT = "tft"


class ForecastModelSelector:
    """
    Deterministically selects the appropriate forecast model
    based on history depth. Selection is versioned and logged.
    """

    THRESHOLDS = {
        ForecastModel.LINEAR_TREND: (0, 12),
        ForecastModel.NBEATS: (12, 24),
        ForecastModel.TFT: (24, float("inf")),
    }

    def select(self, history_months: int, has_covariates: bool = False) -> dict:
        """
        Selects a model for a delegation based on available history.

        Args:
            history_months: number of months of price history available
            has_covariates: whether external covariates are available

        Returns a dict with model choice, reason, and whether conformal prediction is needed.
        """
        for model, (low, high) in self.THRESHOLDS.items():
            if low <= history_months < high:
                return {
                    "model": model.value,
                    "history_months": history_months,
                    "reason": self._reason(model, history_months),
                    "needs_conformal": model != ForecastModel.TFT,
                    # TFT produces native quantiles; others need conformal wrapper
                }

        # Default to TFT for very long histories
        return {
            "model": ForecastModel.TFT.value,
            "history_months": history_months,
            "reason": f"{history_months} months — TFT with full covariates",
            "needs_conformal": False,
        }

    def _reason(self, model: ForecastModel, months: int) -> str:
        """Generate an explanation for the model choice."""
        if model == ForecastModel.LINEAR_TREND:
            return (
                f"Only {months} months of history. "
                "Linear trend is the only statistically safe choice. "
                "Conformal prediction will widen the band appropriately."
            )
        if model == ForecastModel.NBEATS:
            return (
                f"{months} months of history. "
                "N-BEATS learns complex patterns without feature engineering. "
                "Conformal prediction applied for coverage guarantee."
            )
        return (
            f"{months} months of history. "
            "TFT handles seasonality and external covariates natively "
            "and produces calibrated quantile forecasts directly."
        )
