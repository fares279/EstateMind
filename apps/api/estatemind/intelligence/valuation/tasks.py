from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from estatemind.intelligence.valuation.services.calibration_monitor import ValuationCalibrationMonitor
from estatemind.intelligence.valuation.services.drift_monitor import ValuationDriftMonitor

logger = logging.getLogger(__name__)


@shared_task(name='valuation.run_monthly_calibration_monitor')
def run_monthly_calibration_monitor() -> dict:
    monitor = ValuationCalibrationMonitor()
    from estatemind.intelligence.valuation.services.model_registry import ValuationModelRegistry

    registry = ValuationModelRegistry()
    results = []
    for version in registry.list_versions().filter(status='champion'):
        result = monitor.run_calibration_check(version.id)
        results.append(result)
        logger.info('Calibration monitor for version %s: %s', version.id, result.get('status', 'unknown'))
    return {'status': 'completed', 'results': results}


@shared_task(name='valuation.run_weekly_drift_monitor')
def run_weekly_drift_monitor() -> dict:
    monitor = ValuationDriftMonitor()
    from estatemind.intelligence.valuation.services.model_registry import ValuationModelRegistry

    registry = ValuationModelRegistry()
    results = []
    for version in registry.list_versions().filter(status='champion'):
        result = monitor.run(version.id)
        monitor.persist_profile(version.id, result)
        results.append(result)
        logger.info('Drift monitor for version %s complete', version.id)
    return {'status': 'completed', 'results': results}


@shared_task(name='valuation.sync_registry_from_artifacts')
def sync_registry_from_artifacts() -> dict:
    """Best-effort registry sync so prediction logs can attach model provenance."""
    from estatemind.intelligence.valuation.services.model_registry import ValuationModelRegistry

    registry = ValuationModelRegistry()
    handles = registry._artifact_registry.list_handles()
    created = 0
    for index, handle in enumerate(handles, start=1):
        if not handle.path.exists():
            continue
        model_name = handle.model_name or f'CatBoost_{handle.property_type.title()}'
        version = f'artifact-{index}'
        version_obj = registry.register_challenger(
            artifact_path=str(handle.path),
            model_name=model_name,
            version=version,
            training_date=timezone.localdate(),
            training_data_hash='',
            training_samples=0,
            eval_rmse=handle.metrics.get('rmse', 0),
            eval_r2=handle.metrics.get('r2', 0),
            eval_mape=handle.metrics.get('mape', 0),
            eval_holdout_size=handle.metrics.get('holdout_size', 0),
            status='champion' if created == 0 else 'challenger',
            ab_traffic_pct=100 if created == 0 else 10,
            notes='Auto-synced from artifact discovery.',
        )
        created += 1
    return {'status': 'completed', 'created': created}
