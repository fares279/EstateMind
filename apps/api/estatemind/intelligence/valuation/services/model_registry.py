from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from types import SimpleNamespace

from django.utils import timezone

from config.paths import resolve_artifact_ref, to_artifact_ref

from estatemind.market.core.models import DelegationMarketSnapshot
from estatemind.intelligence.valuation.models import ValuationModelVersion
from estatemind.intelligence.valuation.inference.model_registry import (
    ModelHandle,
    ModelRegistry as ArtifactModelRegistry,
)

logger = logging.getLogger(__name__)


class ValuationModelRegistry:
    """DB-backed model registry with artifact-discovery fallback."""

    def __init__(self, manifest_path: str | Path | None = None) -> None:
        self._artifact_registry = ArtifactModelRegistry(manifest_path=manifest_path)

    def list_versions(self, model_name: str | None = None):
        qs = ValuationModelVersion.objects.all()
        if model_name:
            qs = qs.filter(model_name=model_name)
        return qs.order_by('-created_at')

    def _lookup_model_name(self, property_type: str) -> str:
        ptype = str(property_type or 'apartment').strip().lower()
        return f'CatBoost_{ptype.title()}'

    def _version_to_handle(self, version: ValuationModelVersion) -> ModelHandle:
        path = resolve_artifact_ref(version.artifact_path)
        return ModelHandle(
            scope='registry',
            property_type=version.model_name.replace('CatBoost_', '').lower(),
            model_name=version.model_name,
            path=path,
            metrics={
                'eval_rmse': version.eval_rmse,
                'eval_r2': version.eval_r2,
                'eval_mape': version.eval_mape,
                'eval_holdout_size': version.eval_holdout_size,
                'status': version.status,
            },
        )

    def _get_version_for_property(self, property_type: str, user_id: int | None = None) -> ValuationModelVersion | None:
        model_name = self._lookup_model_name(property_type)
        champion = ValuationModelVersion.objects.filter(model_name=model_name, status='champion').order_by('-promoted_at', '-created_at').first()
        challenger = ValuationModelVersion.objects.filter(model_name=model_name, status='challenger').order_by('-promoted_at', '-created_at').first()
        if challenger and user_id is not None and user_id % 10 == 0:
            return challenger
        return champion or challenger

    def get_active_model(self, property_type: str, user_id: int | None = None) -> tuple[ModelHandle | None, ValuationModelVersion | None]:
        version = self._get_version_for_property(property_type, user_id=user_id)
        if version:
            return self._version_to_handle(version), version

        handle = self._artifact_registry.get_best_handle(property_type)
        if handle is None:
            return None, None
        synthetic_version = SimpleNamespace(
            model_name=handle.model_name or self._lookup_model_name(property_type),
            version=handle.path.stem,
            artifact_path=to_artifact_ref(handle.path),
            training_date=timezone.localdate(),
            eval_rmse=float(handle.metrics.get('rmse', 0) or 0),
            eval_r2=float(handle.metrics.get('r2', 0) or 0),
            eval_mape=float(handle.metrics.get('mape', 0) or 0),
            status='artifact',
            calibration_profile={},
            drift_profile={},
        )
        return handle, synthetic_version

    def get_best_handle(self, property_type: str) -> ModelHandle | None:
        handle, _version = self.get_active_model(property_type)
        return handle

    def maybe_load_bundle(self, handle: ModelHandle | None) -> ModelHandle | None:
        return self._artifact_registry.maybe_load_bundle(handle)

    def latest_snapshot_date(self):
        return (
            DelegationMarketSnapshot.objects.order_by('-as_of_date')
            .values_list('as_of_date', flat=True)
            .first()
        )

    def promote(self, version_id: int, promoted_by: str = '') -> ValuationModelVersion:
        version = ValuationModelVersion.objects.get(pk=version_id)
        ValuationModelVersion.objects.filter(model_name=version.model_name, status='champion').update(status='retired')
        version.status = 'champion'
        version.ab_traffic_pct = 100
        version.promoted_by = promoted_by
        version.promoted_at = timezone.now()
        version.save(update_fields=['status', 'ab_traffic_pct', 'promoted_by', 'promoted_at', 'updated_at'])
        return version

    def register_challenger(self, artifact_path: str, model_name: str, version: str, **metrics: Any) -> ValuationModelVersion:
        obj, _ = ValuationModelVersion.objects.update_or_create(
            model_name=model_name,
            version=version,
            defaults={
                'artifact_path': artifact_path,
                'training_date': metrics.get('training_date') or timezone.localdate(),
                'training_data_hash': metrics.get('training_data_hash') or '',
                'training_samples': metrics.get('training_samples') or 0,
                'eval_rmse': metrics.get('eval_rmse') or 0,
                'eval_r2': metrics.get('eval_r2') or 0,
                'eval_mape': metrics.get('eval_mape') or 0,
                'eval_holdout_size': metrics.get('eval_holdout_size') or 0,
                'status': metrics.get('status') or 'challenger',
                'ab_traffic_pct': metrics.get('ab_traffic_pct') or 10,
                'notes': metrics.get('notes') or '',
            },
        )
        return obj
