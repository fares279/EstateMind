from __future__ import annotations

import logging
from datetime import timedelta

import numpy as np
from django.db.models import F
from django.utils import timezone
from sklearn.isotonic import IsotonicRegression

from estatemind.intelligence.valuation.models import ValuationModelVersion, ValuationPredictionLog

logger = logging.getLogger(__name__)


class ValuationCalibrationMonitor:
    """Monthly confidence calibration audit and optional isotonic correction."""

    TOLERANCE_PCT = 5.0
    MIN_SAMPLE_SIZE = 50

    def _confidence_to_level(self, confidence_level: str | None, prediction_tnd: float, low: float, high: float) -> float:
        label = str(confidence_level or '').lower()
        if 'high' in label:
            return 0.80
        if 'medium' in label:
            return 0.70
        if 'low' in label:
            return 0.60
        band_ratio = (high - low) / max(prediction_tnd, 1.0)
        if band_ratio < 0.12:
            return 0.80
        if band_ratio < 0.20:
            return 0.70
        return 0.60

    def run_calibration_check(self, model_version_id: int, lookback_days: int = 90) -> dict:
        cutoff = timezone.now() - timedelta(days=lookback_days)
        logs = list(
            ValuationPredictionLog.objects.filter(
                model_version_id=model_version_id,
                created_at__gte=cutoff,
                actual_tnd__isnull=False,
            ).values('prediction_tnd', 'confidence_low', 'confidence_high', 'confidence_level', 'actual_tnd')
        )
        if len(logs) < self.MIN_SAMPLE_SIZE:
            return {'status': 'insufficient_data', 'sample_size': len(logs), 'model_version_id': model_version_id}

        buckets: dict[str, dict] = {}
        raw_levels = []
        actual_hits = []
        for row in logs:
            stated_level = self._confidence_to_level(row['confidence_level'], row['prediction_tnd'], row['confidence_low'], row['confidence_high'])
            in_band = row['confidence_low'] <= row['actual_tnd'] <= row['confidence_high']
            key = f"conf_{int(stated_level * 100)}"
            bucket = buckets.setdefault(key, {'stated': stated_level, 'sample': 0, 'hits': 0})
            bucket['sample'] += 1
            bucket['hits'] += int(in_band)
            raw_levels.append(stated_level)
            actual_hits.append(1.0 if in_band else 0.0)

        for key, bucket in buckets.items():
            observed = bucket['hits'] / max(bucket['sample'], 1)
            gap = observed - bucket['stated']
            bucket.update({
                'observed': round(observed, 3),
                'gap': round(gap, 3),
                'status': 'ok' if abs(gap * 100) <= self.TOLERANCE_PCT else ('overconfident' if gap < 0 else 'underconfident'),
            })

        needs_correction = any(abs(bucket['gap'] * 100) > self.TOLERANCE_PCT for bucket in buckets.values())
        calibrator = self.apply_isotonic_correction(np.array(raw_levels), np.array(actual_hits)) if len(set(raw_levels)) > 1 else None
        profile = self._build_profile(buckets, calibrator)

        version = ValuationModelVersion.objects.filter(pk=model_version_id).first()
        if version:
            version.calibration_profile = profile
            version.save(update_fields=['calibration_profile', 'updated_at'])

        return {
            'model_version_id': model_version_id,
            'buckets': buckets,
            'needs_correction': needs_correction,
            'calibration_profile': profile,
            'checked_at': timezone.now().isoformat(),
        }

    def apply_isotonic_correction(self, raw_confidences: np.ndarray, observed_accuracies: np.ndarray) -> IsotonicRegression:
        calibrator = IsotonicRegression(out_of_bounds='clip')
        calibrator.fit(raw_confidences, observed_accuracies)
        return calibrator

    def _build_profile(self, buckets: dict[str, dict], calibrator: IsotonicRegression | None) -> dict:
        if not buckets:
            return {'confidence_map': {}, 'source': 'none'}
        confidence_map = {str(bucket['stated']): bucket['observed'] for bucket in buckets.values()}
        profile = {
            'confidence_map': confidence_map,
            'buckets': buckets,
            'source': 'isotonic' if calibrator is not None else 'empirical',
        }
        if calibrator is not None:
            grid = np.linspace(0.6, 0.9, 7)
            profile['isotonic_curve'] = {
                'raw': [round(float(x), 3) for x in grid],
                'calibrated': [round(float(y), 3) for y in calibrator.predict(grid)],
            }
        return profile

    def apply_profile(self, confidence_result: dict, profile: dict | None) -> dict:
        if not profile:
            return confidence_result
        confidence = float(confidence_result.get('confidence', 0))
        confidence_map = profile.get('confidence_map', {}) if isinstance(profile, dict) else {}
        if confidence_map:
            keys = sorted(float(key) for key in confidence_map.keys())
            target = max(k for k in keys if k * 100 <= confidence) if keys else None
            if target is not None:
                mapped = float(confidence_map.get(str(target), confidence / 100.0)) * 100.0
                adjustment = mapped - confidence
                confidence_result = dict(confidence_result)
                confidence_result['confidence'] = int(round(mapped))
                ratio = max(0.6, min(1.4, 1.0 - (adjustment / 250.0)))
                confidence_result['lower_bound'] = round(float(confidence_result['lower_bound']) * ratio)
                confidence_result['upper_bound'] = round(float(confidence_result['upper_bound']) * (2 - ratio))
        confidence_result['calibration_profile'] = profile
        return confidence_result
