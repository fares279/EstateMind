from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from config.paths import to_artifact_ref

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
    """Register discovered artifacts, one registry key per serving scope.

    A scope with no champion gets the artifact that discovery serves for it;
    other artifacts are registered as challengers with 0% traffic, so nothing
    new is served until someone promotes it or gives it traffic.
    """
    from estatemind.intelligence.valuation.models import ValuationModelVersion
    from estatemind.intelligence.valuation.services.model_registry import (
        GLOBAL_SCOPE, ValuationModelRegistry, artifact_family, registry_key,
    )

    registry = ValuationModelRegistry()
    artifacts = registry._artifact_registry
    created = 0
    for handle in artifacts.list_handles():
        if not handle.path.exists():
            continue
        scope = GLOBAL_SCOPE if handle.scope == 'global' else handle.property_type
        key = registry_key(scope)
        ref = to_artifact_ref(handle.path)
        if ValuationModelVersion.objects.filter(model_name=key, artifact_path=ref).exists():
            continue
        served = artifacts.get_global_handle() if scope == GLOBAL_SCOPE else artifacts.get_property_handle(scope)
        make_champion = (served is not None and served.path == handle.path
                         and not ValuationModelVersion.objects.filter(model_name=key, status='champion').exists())
        registry.register_challenger(
            artifact_path=ref,
            model_name=key,
            version=f'{artifact_family(ref)}-artifact',
            training_date=timezone.localdate(),
            training_data_hash='',
            training_samples=0,
            eval_rmse=handle.metrics.get('rmse', 0),
            eval_r2=handle.metrics.get('r2', 0),
            eval_mape=handle.metrics.get('mape', 0),
            eval_holdout_size=handle.metrics.get('holdout_size', 0),
            status='champion' if make_champion else 'challenger',
            ab_traffic_pct=100 if make_champion else 0,
            notes=f'Auto-synced from artifact discovery ({handle.path.name}).',
        )
        created += 1
    return {'status': 'completed', 'created': created}
