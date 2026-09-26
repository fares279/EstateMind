from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from typing import Any

from django.utils import timezone

from estatemind.intelligence.valuation.models import ValuationModelVersion, ValuationPredictionLog

logger = logging.getLogger(__name__)


def build_input_hash(data: dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True, default=str, ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def log_prediction(
    *,
    user,
    model_version: ValuationModelVersion | None,
    input_features: dict[str, Any],
    prediction: dict[str, Any],
    result: dict[str, Any],
    latency_ms: int,
    snapshot_date: date | None = None,
    fallback_used: bool = False,
) -> ValuationPredictionLog | None:
    try:
        version_label = ''
        model_name = ''
        db_version = None
        if model_version is not None:
            model_name = getattr(model_version, 'model_name', '') or ''
            version_label = getattr(model_version, 'version', '') or ''
            db_version = model_version if isinstance(model_version, ValuationModelVersion) and getattr(model_version, 'pk', None) else None

        return ValuationPredictionLog.objects.create(
            user=user if getattr(user, 'is_authenticated', False) else None,
            model_version=db_version,
            model_name=model_name or str(result.get('model_info', {}).get('name', '')),
            model_version_label=version_label or str(result.get('model_info', {}).get('version', '')),
            input_hash=build_input_hash(input_features),
            input_features=input_features,
            prediction_tnd=float(result.get('estimated_price', 0) or 0),
            confidence_low=float(result.get('lower_bound', 0) or 0),
            confidence_high=float(result.get('upper_bound', 0) or 0),
            confidence_level=str(result.get('confidence_level', 'Medium')),
            fallback_used=fallback_used,
            latency_ms=max(int(latency_ms), 0),
            snapshot_date=snapshot_date,
            calibration_state='pending',
        )
    except Exception as exc:  # pragma: no cover - logging must never break prediction serving
        logger.warning('Prediction audit log skipped: %s', exc)
        return None


def update_prediction_actual(log: ValuationPredictionLog, actual_tnd: float) -> ValuationPredictionLog:
    log.actual_tnd = actual_tnd
    log.actual_recorded_at = timezone.now()
    log.calibration_state = 'observed'
    log.save(update_fields=['actual_tnd', 'actual_recorded_at', 'calibration_state'])
    return log
