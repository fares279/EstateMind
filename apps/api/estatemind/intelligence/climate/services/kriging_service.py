import logging
import math
from typing import Dict, Any, Optional
from django.utils import timezone
import numpy as np
from scipy.interpolate import RBFInterpolator

logger = logging.getLogger(__name__)


class KrigingClimateService:
    """
    Builds and queries a continuous climate risk surface over Tunisia.
    Uses RBF (thin-plate spline) interpolation as practical kriging approximation.
    Surface is rebuilt after each recalibration cycle.
    Cached in application memory between rebuilds.
    """
    
    _instance = None  # Singleton cache
    _surface = None
    _built_at = None
    _delegation_count = 0
    
    # Tunisia bounding box (approximate)
    TUNISIA_BOUNDS = {
        'lat_min': 30.2, 'lat_max': 37.6,
        'lon_min': 7.5, 'lon_max': 11.6
    }
    
    @classmethod
    def get_instance(cls):
        """Singleton accessor"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def build_surface(self, force_rebuild: bool = False) -> bool:
        """
        Builds the interpolated surface from all delegation climate scores.
        
        Returns True if successful, False if insufficient data.
        Requires minimum 3 delegations with scores and coordinates.
        
        In production, all 264 Tunisian delegations should be present.
        """
        from estatemind.market.core.models import DelegationClimateScore
        
        scores = list(
            DelegationClimateScore.objects
            .select_related('delegation')
            .filter(
                delegation__centroid_lat__isnull=False,
                delegation__centroid_lon__isnull=False
            )
        )
        
        if len(scores) < 3:
            logger.warning(
                f'Cannot build kriging surface: only {len(scores)} '
                f'delegations have scores and coordinates. Need at least 3.'
            )
            return False
        
        try:
            coords = np.array([
                [s.delegation.centroid_lat, s.delegation.centroid_lon]
                for s in scores
            ])
            
            values = np.array([s.composite_score for s in scores])
            
            # Thin-plate spline kernel: C² smooth, no hyperparameters needed
            # smoothing=0.05: slight regularization to handle measurement noise
            # without overfitting to individual delegation scores
            self._surface = RBFInterpolator(
                coords, values,
                kernel='thin_plate_spline',
                smoothing=0.05
            )
            
            self._built_at = timezone.now()
            self._delegation_count = len(scores)
            
            logger.info(
                f'Kriging surface built from {len(scores)} delegation scores. '
                f'Coverage: {len(scores)} / 264 Tunisian delegations '
                f'({len(scores)/264*100:.1f}%)'
            )
            
            return True
        
        except Exception as e:
            logger.error(f'Failed to build kriging surface: {e}')
            return False
    
    def get_point_risk(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Returns interpolated climate risk score at given coordinates.
        
        Validates coordinates are within Tunisia bounds before querying.
        Falls back to nearest delegation if surface unavailable.
        
        Returns dict with:
        - score: interpolated risk score [0, 1] or None if out of bounds
        - risk_label: categorical risk level
        - method: which method was used (kriging, nearest, fallback)
        - Additional metadata about surface quality
        """
        
        # Validate coordinates are within Tunisia
        if not (self.TUNISIA_BOUNDS['lat_min'] <= lat <= self.TUNISIA_BOUNDS['lat_max'] and
                self.TUNISIA_BOUNDS['lon_min'] <= lon <= self.TUNISIA_BOUNDS['lon_max']):
            return {
                'score': None,
                'method': 'out_of_bounds',
                'error': f'Coordinates ({lat}, {lon}) are outside Tunisia bounds',
                'risk_label': None
            }
        
        # Build surface if not yet built or needs refresh
        if self._surface is None or self._needs_rebuild():
            success = self.build_surface()
            if not success:
                return self._nearest_delegation_fallback(lat, lon)
        
        try:
            point = np.array([[lat, lon]])
            interpolated = float(self._surface(point)[0])
            
            # Clamp — RBF can extrapolate outside [0, 1] at boundaries
            interpolated = max(0.0, min(1.0, interpolated))
            
            return {
                'score': round(interpolated, 4),
                'method': 'kriging_rbf_thin_plate_spline',
                'risk_label': self._score_to_label(interpolated),
                'coordinates': {'lat': lat, 'lon': lon},
                'surface_built_at': self._built_at.isoformat() if self._built_at else None,
                'surface_delegation_count': self._delegation_count,
                'surface_coverage_pct': round(
                    self._delegation_count / 264 * 100, 1
                )
            }
        
        except Exception as e:
            logger.warning(f'Kriging interpolation failed at ({lat}, {lon}): {e}')
            return self._nearest_delegation_fallback(lat, lon)
    
    def _needs_rebuild(self) -> bool:
        """Surface needs rebuild if more than 24 hours old"""
        if self._built_at is None:
            return True
        age_hours = (timezone.now() - self._built_at).total_seconds() / 3600
        return age_hours > 24
    
    def _nearest_delegation_fallback(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Haversine nearest-neighbor fallback when kriging surface unavailable.
        Explicitly labeled so caller knows it is an approximation.
        """
        from estatemind.market.core.models import DelegationClimateScore
        
        best = None
        best_dist = float('inf')
        
        for score in DelegationClimateScore.objects.select_related('delegation'):
            d = score.delegation
            if not (d.centroid_lat and d.centroid_lon):
                continue
            
            # Haversine distance
            dlat = math.radians(lat - d.centroid_lat)
            dlon = math.radians(lon - d.centroid_lon)
            a = (math.sin(dlat/2)**2 +
                 math.cos(math.radians(lat)) *
                 math.cos(math.radians(d.centroid_lat)) *
                 math.sin(dlon/2)**2)
            dist_km = 6371 * 2 * math.asin(math.sqrt(a))
            
            if dist_km < best_dist:
                best_dist = dist_km
                best = score
        
        if best:
            return {
                'score': best.composite_score,
                'method': 'nearest_delegation_fallback',
                'risk_label': best.risk_label,
                'nearest_delegation': best.delegation.name,
                'distance_km': round(best_dist, 1),
                'note': 'Kriging surface unavailable. '
                       'Score is from nearest delegation centroid.'
            }
        
        return {
            'score': 0.35,
            'method': 'national_average_fallback',
            'risk_label': 'MODERATE',
            'note': 'No delegation scores available. Using national average.'
        }
    
    def _score_to_label(self, score: float) -> str:
        """Convert numeric score [0, 1] to categorical risk label"""
        thresholds = [
            (0.15, 'VERY_LOW'),
            (0.30, 'LOW'),
            (0.45, 'MODERATE'),
            (0.60, 'MODERATE_HIGH'),
            (0.75, 'HIGH'),
            (1.01, 'VERY_HIGH'),
        ]
        for threshold, label in thresholds:
            if score < threshold:
                return label
        return 'VERY_HIGH'
    
    def get_surface_quality_report(self) -> Dict[str, Any]:
        """Return quality indicators for the kriging surface"""
        return {
            'built_at': self._built_at.isoformat() if self._built_at else None,
            'delegation_count': self._delegation_count,
            'coverage_pct': round(self._delegation_count / 264 * 100, 1) if self._delegation_count > 0 else 0,
            'quality': (
                'HIGH' if self._delegation_count >= 200 else
                'MEDIUM' if self._delegation_count >= 100 else
                'LOW' if self._delegation_count > 0 else
                'UNAVAILABLE'
            ),
            'interpolation_method': 'RBF thin-plate spline',
            'smoothing_parameter': 0.05,
            'note': (
                'Surface interpolates between delegation centroids. '
                'Accuracy is highest in delegation interiors and '
                'moderate near boundaries.'
            )
        }
    
    def invalidate(self):
        """Clear the cached surface to force rebuild on next use"""
        self._surface = None
        self._built_at = None
        logger.info('Kriging surface cache invalidated')
