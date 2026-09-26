from __future__ import annotations

from datetime import timedelta

import numpy as np
from django.utils import timezone
from scipy.stats import ks_2samp

from estatemind.intelligence.valuation.models import ValuationModelVersion, ValuationPredictionLog


class ValuationDriftMonitor:
    """Tracks feature drift and confidence/output drift for valuation traffic."""

    PSI_WARN_THRESHOLD = 0.10
    PSI_ALERT_THRESHOLD = 0.20
    KS_P_THRESHOLD = 0.05

    def compute_psi(self, baseline: np.ndarray, current: np.ndarray, buckets: int = 10) -> float:
        bp = np.percentile(baseline, np.linspace(0, 100, buckets + 1))
        bp = np.unique(bp)
        if len(bp) < 2:
            return 0.0
        exp_pct = np.histogram(baseline, bins=bp)[0] / max(len(baseline), 1)
        act_pct = np.histogram(current, bins=bp)[0] / max(len(current), 1)
        exp_pct = np.where(exp_pct == 0, 1e-6, exp_pct)
        act_pct = np.where(act_pct == 0, 1e-6, act_pct)
        return float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct)))

    def _window_logs(self, model_version_id: int, start_days_ago: int, end_days_ago: int | None = None):
        end = timezone.now() - timedelta(days=end_days_ago) if end_days_ago is not None else timezone.now()
        start = timezone.now() - timedelta(days=start_days_ago)
        return list(
            ValuationPredictionLog.objects.filter(
                model_version_id=model_version_id,
                created_at__gte=start,
                created_at__lt=end,
            ).values('input_features', 'confidence_high', 'prediction_tnd')
        )

    def run_input_drift_check(self, model_version_id: int) -> dict:
        recent_logs = self._window_logs(model_version_id, 30)
        baseline_logs = self._window_logs(model_version_id, 60, 30)
        features_to_check = ['surface_m2', 'bedrooms', 'bathrooms', 'image_count']
        report = {}

        for feature in features_to_check:
            baseline = np.array([float((row['input_features'] or {}).get(feature, 0)) for row in baseline_logs if (row['input_features'] or {}).get(feature) is not None])
            current = np.array([float((row['input_features'] or {}).get(feature, 0)) for row in recent_logs if (row['input_features'] or {}).get(feature) is not None])
            if len(baseline) < 10 or len(current) < 10:
                continue
            psi = self.compute_psi(baseline, current)
            report[feature] = {
                'psi': round(psi, 4),
                'status': 'stable' if psi < self.PSI_WARN_THRESHOLD else 'warn' if psi < self.PSI_ALERT_THRESHOLD else 'alert',
            }

        return {
            'model_version_id': model_version_id,
            'features': report,
            'any_alert': any(v['status'] == 'alert' for v in report.values()),
            'checked_at': timezone.now().isoformat(),
        }

    def run_output_drift_check(self, model_version_id: int) -> dict:
        baseline_conf = list(
            ValuationPredictionLog.objects.filter(
                model_version_id=model_version_id,
                created_at__gte=timezone.now() - timedelta(days=60),
                created_at__lt=timezone.now() - timedelta(days=30),
            ).values_list('confidence_high', flat=True)
        )
        current_conf = list(
            ValuationPredictionLog.objects.filter(
                model_version_id=model_version_id,
                created_at__gte=timezone.now() - timedelta(days=30),
            ).values_list('confidence_high', flat=True)
        )
        if len(baseline_conf) < 20 or len(current_conf) < 20:
            return {'status': 'insufficient_data'}
        stat, p_value = ks_2samp(baseline_conf, current_conf)
        return {
            'ks_statistic': round(float(stat), 4),
            'p_value': round(float(p_value), 4),
            'distribution_shifted': bool(p_value < self.KS_P_THRESHOLD),
            'baseline_mean': round(float(np.mean(baseline_conf)), 0),
            'current_mean': round(float(np.mean(current_conf)), 0),
        }

    def run(self, model_version_id: int) -> dict:
        return {
            'input_drift': self.run_input_drift_check(model_version_id),
            'output_drift': self.run_output_drift_check(model_version_id),
            'checked_at': timezone.now().isoformat(),
        }

    def persist_profile(self, model_version_id: int, profile: dict) -> None:
        version = ValuationModelVersion.objects.filter(pk=model_version_id).first()
        if not version:
            return
        version.drift_profile = profile
        version.save(update_fields=['drift_profile', 'updated_at'])
