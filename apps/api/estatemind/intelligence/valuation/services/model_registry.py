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
from estatemind.intelligence.valuation.inference.request_mapper import MODEL_PROPERTY_TYPE_MAP

logger = logging.getLogger(__name__)

REGISTRY_PREFIX = 'valuation:'
GLOBAL_SCOPE = 'global'
_SCOPE_ALIASES = {**MODEL_PROPERTY_TYPE_MAP, 'villa': 'maison', 'all': GLOBAL_SCOPE}


def serving_scope(property_type: str | None) -> str:
    """Scope a model serves: the request mapper's model property type ('appartement',
    'maison', 'terrain', ...) or 'global'. English and French names map to the same scope."""
    ptype = str(property_type or '').strip().lower() or 'appartement'
    return _SCOPE_ALIASES.get(ptype, ptype)


def registry_key(property_type: str | None) -> str:
    """ValuationModelVersion.model_name for every version serving this scope."""
    return f'{REGISTRY_PREFIX}{serving_scope(property_type)}'


def artifact_family(artifact_path: str) -> str:
    """Model family from the artifact filename (bytype__maison__et -> 'et'); 'catboost' otherwise."""
    stem = Path(str(artifact_path).replace('\\', '/')).stem.lower()
    parts = stem.split('__')
    if stem.startswith('bytype__') and len(parts) >= 3:
        return parts[2]
    if stem.startswith('global__') and len(parts) >= 2:
        return parts[1]
    return 'catboost'


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
        return registry_key(property_type)

    def _version_to_handle(self, version: ValuationModelVersion) -> ModelHandle:
        # The handle mirrors what artifact discovery produces (scope, property
        # type, model family): InferenceBundle keys off those, not the registry key.
        scope = version.model_name[len(REGISTRY_PREFIX):] if version.model_name.startswith(REGISTRY_PREFIX)             else serving_scope(version.model_name)
        is_global = scope == GLOBAL_SCOPE
        return ModelHandle(
            scope='global' if is_global else 'by_type',
            property_type='all' if is_global else scope,
            model_name=artifact_family(version.artifact_path),
            path=resolve_artifact_ref(version.artifact_path),
            metrics={
                'eval_rmse': version.eval_rmse,
                'eval_r2': version.eval_r2,
                'eval_mape': version.eval_mape,
                'eval_holdout_size': version.eval_holdout_size,
                'status': version.status,
            },
        )

    def _get_version_for_property(self, property_type: str, user_id: int | None = None) -> ValuationModelVersion | None:
        """Champion for the scope, or a challenger for the share of users its
        ab_traffic_pct asks for (user_id % 100). Scopes without a champion use
        the global champion."""
        for key in dict.fromkeys((registry_key(property_type), registry_key(GLOBAL_SCOPE))):
            versions = ValuationModelVersion.objects.filter(model_name=key).order_by('-promoted_at', '-created_at')
            champion = versions.filter(status='champion').first()
            challenger = versions.filter(status='challenger', ab_traffic_pct__gt=0).first()
            if challenger and user_id is not None and user_id % 100 < challenger.ab_traffic_pct:
                return challenger
            if champion:
                return champion
        return None

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
                'ab_traffic_pct': metrics.get('ab_traffic_pct', 10),
                'notes': metrics.get('notes') or '',
            },
        )
        return obj
