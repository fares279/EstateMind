"""Filesystem locations used across the API.

Kept free of Django imports so training scripts and management commands can
use it before settings are configured. Every location can be overridden with
an environment variable.
"""
from __future__ import annotations

import os
from pathlib import Path

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
