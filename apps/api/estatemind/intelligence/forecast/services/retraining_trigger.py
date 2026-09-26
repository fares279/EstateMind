"""
Automatic retraining trigger using Kolmogorov-Smirnov two-sample test.

Detects when the market has shifted enough that a forecast model
should be retrained. Uses the KS test to compare the distribution
of training prices vs. recent prices. If distributions differ
significantly, queues a retraining task.
"""

import logging
from scipy.stats import ks_2samp
import numpy as np

logger = logging.getLogger(__name__)


class ForecastRetrainingTrigger:
    """
    Detects when the market has shifted enough that a forecast model
    should be retrained.

    Uses the Kolmogorov-Smirnov two-sample test:
        H0: new price data comes from the same distribution as training data
        H1: distributions are different → market has shifted

    If p-value < 0.05: reject H0 → queue retraining
    """

    KS_P_THRESHOLD = 0.05
    MIN_SAMPLE_SIZE = 12  # months needed for reliable KS test
    COOLDOWN_MONTHS = 3  # don't retrain more than once per quarter

    def check(
        self,
        delegation: str,
        property_type: str,
        training_prices: list,
        recent_prices: list,
    ) -> dict:
        """
        Check whether the market distribution has shifted.

        Args:
            delegation: delegation name
            property_type: 'apartment', 'villa', 'land', etc.
            training_prices: prices from the model's training window
            recent_prices: most recent N months of actual prices

        Returns a retraining decision dict with full audit trail.
        """
        if len(training_prices) < self.MIN_SAMPLE_SIZE or len(
            recent_prices
        ) < self.MIN_SAMPLE_SIZE:
            return {
                "should_retrain": False,
                "reason": "insufficient_data",
                "delegation": delegation,
                "property_type": property_type,
            }

        stat, p_value = ks_2samp(training_prices, recent_prices)

        distribution_shifted = p_value < self.KS_P_THRESHOLD

        # Compute descriptive statistics for audit log
        train_mean = float(np.mean(training_prices))
        recent_mean = float(np.mean(recent_prices))
        price_change = (
            (recent_mean - train_mean) / train_mean * 100
            if train_mean > 0
            else 0
        )

        reason = (
            f"KS-test p={p_value:.4f} < {self.KS_P_THRESHOLD} — "
            f"price distribution shifted from mean {train_mean:.0f} "
            f"to {recent_mean:.0f} ({price_change:+.1f}%). Retraining queued."
            if distribution_shifted
            else f"KS-test p={p_value:.4f} ≥ {self.KS_P_THRESHOLD} — "
            "distribution stable, no retraining needed."
        )

        return {
            "delegation": delegation,
            "property_type": property_type,
            "should_retrain": distribution_shifted,
            "ks_statistic": round(stat, 4),
            "p_value": round(p_value, 4),
            "distribution_shifted": distribution_shifted,
            "training_mean": round(train_mean, 2),
            "recent_mean": round(recent_mean, 2),
            "price_change_pct": round(price_change, 1),
            "reason": reason,
        }
