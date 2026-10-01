"""
Conformal calibration orchestration for forecast uncertainty quantification.

Coordinates:
  1. Loading backtest residuals from ForecastModelVersion registry
  2. Calibrating ConformalPredictor on those residuals
  3. Caching calibrated predictors in memory (per session)
  4. Serving prediction intervals with mathematical coverage guarantees

Every delegation × property_type with backtest data gets its own calibrated
conformal predictor tuned to that property's specific error distribution.
"""

import logging
from typing import Optional, Dict, Tuple
from django.core.cache import cache

from estatemind.intelligence.forecast.services.conformal_predictor import ConformalPredictor

logger = logging.getLogger(__name__)

# Cache keys
CONFORMAL_CACHE_PREFIX = "conformal_predictor"
CACHE_TIMEOUT = 3600  # 1 hour


class ConformalCalibratorOrchestrator:
    """
    Manages calibration and serving of conformal predictors across all
    delegation × property_type combinations.
    
    Workflow:
      1. Query ForecastModelVersion for a delegation×property_type
      2. If conformal_residuals exist, calibrate ConformalPredictor
      3. Cache the predictor for repeated use
      4. When serving forecasts, apply predict_interval()
    """

    def __init__(self, coverage: float = 0.90):
        """
        Args:
            coverage: desired coverage level (e.g. 0.90 for 90%)
        """
        self.coverage = coverage

    def get_or_calibrate_predictor(
        self, delegation_name: str, property_type: str
    ) -> Optional[Tuple[ConformalPredictor, Dict]]:
        """
        Retrieves a cached conformal predictor or calibrates a new one.

        Args:
            delegation_name: e.g. 'Tunis'
            property_type: e.g. 'apartment'

        Returns:
            (ConformalPredictor, calibration_metadata) if successful,
            None if no backtest residuals available
        """
        cache_key = self._cache_key(delegation_name, property_type)
        cached = cache.get(cache_key)
        if cached is False:  # known to have no residuals (a forecast asks once per month)
            return None
        if cached:
            return cached

        # Load backtest residuals from registry
        from estatemind.intelligence.forecast.models import ForecastModelVersion
        
        model_version = (
            ForecastModelVersion.objects
            .filter(
                delegation_name__iexact=delegation_name,
                property_type=property_type,
                is_active=True,
            )
            .order_by('-created_at')
            .first()
        )

        if not model_version or not model_version.conformal_residuals:
            # remembered, so one forecast doesn't repeat the query and log it ~24 times
            cache.set(cache_key, False, CACHE_TIMEOUT)
            logger.debug("No conformal residuals for %s / %s", delegation_name, property_type)
            return None

        # Calibrate predictor on residuals
        predictor = ConformalPredictor(coverage=self.coverage)
        # The backtester emits one residual per test month, 12 per window, in order.
        residuals = model_version.conformal_residuals
        horizons = [i % 12 + 1 for i in range(len(residuals))]
        calibration_metadata = predictor.calibrate(residuals, horizons=horizons)

        # Cache result
        result = (predictor, calibration_metadata)
        cache.set(cache_key, result, CACHE_TIMEOUT)

        logger.info(
            "Calibrated conformal predictor for %s / %s (quantile=%.2f, n_samples=%d)",
            delegation_name,
            property_type,
            calibration_metadata.get("quantile", 0),
            calibration_metadata.get("calibration_samples", 0),
        )

        return result

    def predict_with_intervals(
        self, delegation_name: str, property_type: str, point_forecast: float, horizon: int | None = None
    ) -> Optional[Dict]:
        """
        Wraps a point forecast with calibrated conformal prediction intervals.

        Args:
            delegation_name: e.g. 'Tunis'
            property_type: e.g. 'apartment'
            point_forecast: point estimate in TND/m²

        Returns:
            dict with point, low, high, quantile, coverage, width_pct, label
            or None if no calibration available
        """
        result = self.get_or_calibrate_predictor(delegation_name, property_type)
        if not result:
            return None

        predictor, metadata = result
        return predictor.predict_interval(point_forecast, horizon=horizon)

    def predict_quantile_fan(
        self,
        delegation_name: str,
        property_type: str,
        point_forecast: float,
        levels: list = None,
    ) -> Optional[list]:
        """
        Produces a quantile fan for fan chart rendering.

        Args:
            delegation_name: e.g. 'Tunis'
            property_type: e.g. 'apartment'
            point_forecast: point estimate in TND/m²
            levels: coverage levels (default: [0.50, 0.70, 0.80, 0.90])

        Returns:
            list of dicts with coverage, low, high for each level
            or None if no calibration available
        """
        result = self.get_or_calibrate_predictor(delegation_name, property_type)
        if not result:
            return None

        predictor, metadata = result
        return predictor.predict_quantile_fan(point_forecast, levels)

    def get_calibration_metadata(
        self, delegation_name: str, property_type: str
    ) -> Optional[Dict]:
        """
        Returns calibration metadata without needing the predictor itself.
        Useful for API responses that want to signal "this forecast has
        been conformal calibrated" without sending the full calibration data.
        """
        result = self.get_or_calibrate_predictor(delegation_name, property_type)
        if not result:
            return None

        predictor, metadata = result
        return {
            "quantile": metadata.get("quantile"),
            "coverage": metadata.get("coverage"),
            "calibration_samples": metadata.get("calibration_samples"),
            "residual_p50": metadata.get("residual_p50"),
            "residual_p90": metadata.get("residual_p90"),
            "valid": metadata.get("valid"),
        }

    def _cache_key(self, delegation_name: str, property_type: str) -> str:
        """Generate a cache key for this predictor combination."""
        # Sanitize cache key by replacing spaces with underscores to avoid caching issues
        delegation_safe = delegation_name.lower().replace(' ', '_')
        property_safe = property_type.lower().replace(' ', '_')
        return f"{CONFORMAL_CACHE_PREFIX}:{delegation_safe}:{property_safe}"

    def invalidate_cache(self, delegation_name: str = None, property_type: str = None):
        """
        Invalidate cached predictors when backtest results are updated.
        
        Args:
            delegation_name: if None, invalidates all
            property_type: if None, invalidates all for the delegation
        """
        if delegation_name is None:
            # Invalidate entire conformal cache
            from django.core.cache import cache
            cache.delete_many([
                k for k in cache.keys("*")
                if k.startswith(CONFORMAL_CACHE_PREFIX)
            ])
            logger.info("Invalidated all conformal predictors")
        else:
            cache_key = self._cache_key(delegation_name, property_type or "*")
            cache.delete(cache_key)
            logger.info("Invalidated conformal predictor: %s", cache_key)
