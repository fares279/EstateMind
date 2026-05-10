"""Model artifact discovery and lazy loading for valuation serving.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .inference_bundle import InferenceBundle, load_reference_dataset

try:
    import joblib
except ModuleNotFoundError:  # pragma: no cover
    joblib = None  # type: ignore[assignment]


def project_root() -> Path:
    """Return the repository root used to resolve relative artifact paths."""

    # backend/valuation/inference -> parents[3] = repository root
    return Path(__file__).resolve().parents[3]


@dataclass
class ModelHandle:
    scope: str
    property_type: str
    model_name: str
    path: Path
    metrics: dict[str, Any]
    estimator: Any | None = None
    load_error: str | None = None
    bundle: InferenceBundle | None = None
    bundle_error: str | None = None

    @property
    def available(self) -> bool:
        return self.path.exists() and self.load_error is None

    @property
    def bundle_available(self) -> bool:
        return self.bundle is not None and self.bundle_error is None


class ModelRegistry:
    def __init__(self, manifest_path: str | Path | None = None) -> None:
        root = project_root()
        default_manifest = root / "artifacts" / "reports" / "ml_reports" / "training_estateprocessor_manifest.json"
        self.manifest_path = Path(manifest_path) if manifest_path else default_manifest
        self.root = root
        self._handles = self._load_manifest()
        self._reference_df: Any | None = None

    def _load_manifest(self) -> list[ModelHandle]:
        if not self.manifest_path.exists():
            return self._discover_handles()
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        handles: list[ModelHandle] = []
        for item in payload:
            rel_path = Path(str(item.get("path", "")))
            resolved = self.root / rel_path
            if not resolved.exists() and "artifacts\\models_estateprocessor" in str(rel_path).replace("/", "\\"):
                alt_rel = Path(str(rel_path).replace("artifacts\\models_estateprocessor", "artifacts\\models\\models_estateprocessor"))
                alt_resolved = self.root / alt_rel
                if alt_resolved.exists():
                    resolved = alt_resolved
            handles.append(
                ModelHandle(
                    scope=str(item.get("scope", "")),
                    property_type=str(item.get("property_type", "")),
                    model_name=str(item.get("model_name", "")),
                    path=resolved,
                    metrics=dict(item.get("metrics", {})),
                )
            )
        return handles

    def _discover_handles(self) -> list[ModelHandle]:
        handles: list[ModelHandle] = []
        artifact_roots = [
            self.root / "backend" / "valuation" / "artifacts" / "models" / "models_estateprocessor",
            self.root / "backend" / "valuation" / "artifacts" / "models_estateprocessor",
            self.root / "frontend" / "repo_clone" / "artifacts" / "models" / "models_estateprocessor",
            self.root / "artifacts" / "models" / "models_estateprocessor",
        ]
        for artifact_root in artifact_roots:
            if not artifact_root.exists():
                continue
            for artifact in artifact_root.glob("*.joblib"):
                stem = artifact.stem.lower()
                if stem.startswith("bytype__"):
                    parts = stem.split("__")
                    if len(parts) >= 3:
                        handles.append(
                            ModelHandle(
                                scope="by_type",
                                property_type=parts[1],
                                model_name=parts[2],
                                path=artifact,
                                metrics={},
                            )
                        )
                elif stem.startswith("global__"):
                    parts = stem.split("__")
                    handles.append(
                        ModelHandle(
                            scope="global",
                            property_type="all",
                            model_name=parts[1] if len(parts) >= 2 else "catboost",
                            path=artifact,
                            metrics={},
                        )
                    )
        return handles

    def list_handles(self) -> list[ModelHandle]:
        return list(self._handles)

    def get_property_handle(self, property_type: str) -> ModelHandle | None:
        wanted = str(property_type).strip().lower()
        for handle in self._handles:
            if handle.scope == "by_type" and handle.property_type.strip().lower() == wanted:
                return handle
        return None

    def get_global_handle(self) -> ModelHandle | None:
        for handle in self._handles:
            if handle.scope == "global":
                return handle
        return None

    def get_best_handle(self, property_type: str) -> ModelHandle | None:
        return self.get_property_handle(property_type) or self.get_global_handle()

    def maybe_load_estimator(self, handle: ModelHandle | None) -> ModelHandle | None:
        if handle is None or handle.estimator is not None or handle.load_error is not None:
            return handle
        if not handle.path.exists():
            handle.load_error = f"Missing model artifact: {handle.path}"
            return handle
        if joblib is None:
            handle.load_error = "joblib is not installed"
            return handle
        try:
            handle.estimator = joblib.load(handle.path)
        except Exception as exc:  # pragma: no cover
            handle.load_error = str(exc)
        return handle

    def _get_reference_df(self) -> Any:
        if self._reference_df is None:
            try:
                self._reference_df = load_reference_dataset()
            except FileNotFoundError:
                self._reference_df = None
        return self._reference_df

    def maybe_load_bundle(self, handle: ModelHandle | None) -> ModelHandle | None:
        handle = self.maybe_load_estimator(handle)
        if handle is None or handle.bundle is not None or handle.bundle_error is not None:
            return handle
        if handle.load_error is not None:
            handle.bundle_error = handle.load_error
            return handle
        try:
            reference_df = self._get_reference_df()
            handle.bundle = InferenceBundle.from_handle(handle, reference_df)
        except Exception as exc:
            handle.bundle_error = str(exc)
        return handle
