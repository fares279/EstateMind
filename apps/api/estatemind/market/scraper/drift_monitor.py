"""Drift monitoring utilities: PSI and KS-test implementations."""
from __future__ import annotations

from typing import Dict, Any
import numpy as np
from scipy.stats import ks_2samp


def compute_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """
    Compute Population Stability Index (PSI) comparing expected (baseline)
    distribution to actual (current) distribution.

    Returns a float psi score.
    """
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)

    if expected.size == 0 or actual.size == 0:
        return 0.0

    # Build bins based on expected quantiles so we compare like-for-like
    breakpoints = np.percentile(expected, np.linspace(0, 100, buckets + 1))
    # Ensure unique bin edges
    breakpoints = np.unique(breakpoints)
    if breakpoints.size <= 1:
        return 0.0

    exp_hist, _ = np.histogram(expected, bins=breakpoints)
    act_hist, _ = np.histogram(actual, bins=breakpoints)

    exp_pct = exp_hist.astype(float) / exp_hist.sum()
    act_pct = act_hist.astype(float) / act_hist.sum()

    # Replace zeros to avoid log(0)
    exp_pct = np.where(exp_pct == 0, 1e-6, exp_pct)
    act_pct = np.where(act_pct == 0, 1e-6, act_pct)

    psi = np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))
    return float(psi)


def compute_ks_test(baseline: np.ndarray, current: np.ndarray) -> Dict[str, Any]:
    """Run two-sample KS test and return stats dict."""
    baseline = np.asarray(baseline, dtype=float)
    current = np.asarray(current, dtype=float)
    if baseline.size == 0 or current.size == 0:
        return {"ks_statistic": 0.0, "p_value": 1.0, "distribution_shifted": False}

    stat, p_value = ks_2samp(baseline, current)
    return {"ks_statistic": float(stat), "p_value": float(p_value), "distribution_shifted": float(p_value) < 0.05}


def run_ingestion_drift_check(baseline_vals: np.ndarray, current_vals: np.ndarray) -> Dict[str, Any]:
    """Convenience wrapper returning psi, ks, and flag."""
    psi = compute_psi(baseline_vals, current_vals)
    ks = compute_ks_test(baseline_vals, current_vals)
    alert = psi > 0.2 or ks.get('distribution_shifted', False)
    return {
        'psi': round(float(psi), 4),
        'ks': ks,
        'alert': bool(alert),
    }
