"""Filesystem locations used across the API.

Kept free of Django imports so training scripts and management commands can
use it before settings are configured. Every location can be overridden with
an environment variable.
"""
from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath

# apps/api/
API_ROOT = Path(__file__).resolve().parent.parent

# Seed/reference data that ships with the code (delegations.csv, ...).
DATA_DIR = Path(os.environ.get("ESTATEMIND_DATA_DIR", API_ROOT / "data"))

# Trained models and vector stores. Gitignored; regenerate with the training
# and indexing management commands (see docs/ml.md).
ARTIFACTS_DIR = Path(os.environ.get("ESTATEMIND_ARTIFACTS_DIR", API_ROOT / "artifacts"))

# Datasets that lived outside the original backend/ folder (e.g. the
# Price-Trend-Forecasting project). Not present in this repository.
EXTERNAL_DATA_DIR = Path(os.environ.get("ESTATEMIND_EXTERNAL_DATA_DIR", DATA_DIR / "external"))

CHROMA_DIR = ARTIFACTS_DIR / "chroma"


# ── Artifact references stored in the database ───────────────────────────────
# Registries store paths relative to ARTIFACTS_DIR so a database moves between
# machines and containers. Older rows hold absolute paths from wherever the
# model was trained (e.g. C:\...\backend\valuation\artifacts\models\x.joblib).

_LEGACY_APP_ARTIFACT_DIRS = ("valuation", "forecast", "features")


def to_artifact_ref(path) -> str:
    """Path to store in a registry row: relative to ARTIFACTS_DIR when inside it."""
    p = Path(path)
    try:
        return p.resolve().relative_to(ARTIFACTS_DIR.resolve()).as_posix()
    except ValueError:
        return str(path)


def resolve_artifact_ref(ref) -> Path:
    """Filesystem path for a stored artifact reference (relative or legacy absolute)."""
    p = Path(str(ref))
    # PureWindowsPath: rows written on Windows must still read as absolute on Linux.
    if not (p.is_absolute() or PureWindowsPath(str(ref)).is_absolute()):
        return ARTIFACTS_DIR / p
    if p.exists():
        return p
    parts = [s for s in str(ref).replace("\\", "/").split("/") if s]
    for i in range(len(parts) - 1):
        if parts[i] in _LEGACY_APP_ARTIFACT_DIRS and parts[i + 1] == "artifacts":
            return ARTIFACTS_DIR.joinpath(parts[i], *parts[i + 2:])
    return p
