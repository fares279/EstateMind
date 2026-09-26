from __future__ import annotations

from datetime import timedelta

import numpy as np
from django.utils import timezone

from estatemind.market.core.models import DelegationMarketSnapshot


class KPIAnomalyDetector:
    """Simple rolling z-score detector for dashboard KPIs."""

    ANOMALY_THRESHOLD = 3.0
    HISTORY_DAYS = 90
    MIN_HISTORY_ROWS = 7

    def check(self, kpi_name: str, new_value: float) -> dict:
        history = self._load_history(kpi_name)

        if len(history) < self.MIN_HISTORY_ROWS:
            return {
                'anomaly': False,
                'reason': 'insufficient_history',
                'z_score': None,
                'published': True,
            }

        mean = float(np.mean(history))
        std = float(np.std(history))

        if std < 1e-6:
            return {
                'anomaly': False,
                'reason': 'zero_variance',
                'z_score': None,
                'published': True,
            }

        z_score = abs((new_value - mean) / std)
        is_anomaly = z_score > self.ANOMALY_THRESHOLD

        return {
            'anomaly': is_anomaly,
            'z_score': round(z_score, 2),
            'mean': round(mean, 2),
            'std': round(std, 2),
            'new_value': new_value,
            'published': not is_anomaly,
            'reason': 'z_score_exceeded' if is_anomaly else 'normal',
        }

    def _load_history(self, kpi_name: str) -> list[float]:
        since = timezone.now() - timedelta(days=self.HISTORY_DAYS)

        if kpi_name == 'national_median_price':
            return [
                float(v)
                for v in DelegationMarketSnapshot.objects
                .filter(updated_at__gte=since)
                .exclude(median_price_per_sqm__isnull=True)
                .values_list('median_price_per_sqm', flat=True)
                .order_by('updated_at')
            ]

        return []
