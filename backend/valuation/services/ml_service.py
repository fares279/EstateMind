"""
ML-based property valuation service.

Loads the trained gradient-boosting model from backend/valuation/artifacts/
and predicts price_per_m² given property features.  Falls back silently when
the model artifact is absent so the heuristic pipeline is always available.
"""
from __future__ import annotations
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ARTIFACTS = Path(__file__).resolve().parents[1] / 'artifacts'
_MODEL_PATH = _ARTIFACTS / 'valuation_model.joblib'


@lru_cache(maxsize=1)
def _load_model():
    """Load and cache the model bundle. Returns None if unavailable."""
    try:
        import joblib
    except ImportError:
        logger.warning('joblib not installed — ML valuation disabled')
        return None

    if not _MODEL_PATH.exists():
        logger.info('Valuation ML model not found at %s — using heuristic', _MODEL_PATH)
        return None

    try:
        bundle = joblib.load(_MODEL_PATH)
        logger.info(
            'Valuation ML model loaded (version=%s, train_mae=%.0f TND/m²)',
            bundle.get('version', 'v1'),
            bundle.get('train_mae', 0),
        )
        return bundle
    except Exception as exc:
        logger.warning('Failed to load valuation ML model: %s', exc)
        return None


# ── Type normalisation shared with heuristic.py ───────────────────────────────
_TYPE_ALIAS = {'villa': 'house', 'office': 'commercial', 'farm': 'commercial'}


def predict(data: dict) -> Optional[dict]:
    """
    Predict price_per_m² using the trained ML model.

    Returns a dict compatible with heuristic.estimate(), or None when the
    model is unavailable so the caller can fall back to heuristic logic.
    """
    bundle = _load_model()
    if bundle is None:
        return None

    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        return None

    model        = bundle['model']
    feature_cols = bundle['feature_cols']
    cat_cols     = bundle.get('cat_cols', [])

    ptype_raw = (data.get('property_type') or 'apartment').lower().strip()
    ptype     = _TYPE_ALIAS.get(ptype_raw, ptype_raw)
    gov       = (data.get('governorate') or '').strip()
    city      = (data.get('delegation') or data.get('city') or '').strip()
    tx_type   = (data.get('transaction_type') or 'sale').lower().strip()
    size_m2   = float(data.get('size_m2') or 100)
    bedrooms  = float(data.get('bedrooms') or 0)
    bathrooms = float(data.get('bathrooms') or 0)

    row = {
        'property_type':    ptype,
        'governorate':      gov,
        'city':             city,
        'transaction_type': tx_type,
        'surface_m2':       size_m2,
        'bedrooms':         bedrooms,
        'bathrooms':        bathrooms,
    }

    try:
        X = pd.DataFrame([row]).reindex(columns=feature_cols)
        for col in cat_cols:
            if col in X.columns:
                X[col] = X[col].fillna('unknown').astype(str)

        ppm2 = float(model.predict(X)[0])

        if ppm2 < 50 or ppm2 > 50_000:
            logger.warning('ML predicted ppm2=%s out of range — skipping', ppm2)
            return None

        total = round(ppm2 * size_m2)
        return {
            'estimated_price':   total,
            'price_per_m2':      round(ppm2, 1),
            'base_price_per_m2': round(ppm2, 1),
            'gov_multiplier':    1.0,
            'deleg_adj':         0.0,
            'size_factor':       1.0,
            'condition_adj':     0.0,
            'amenity_total':     0.0,
            'desc_bonus':        0.0,
            'base_total':        total,
            'contributions':     {'ml_model': total},
            'active_amenities':  [],
            'prediction_mode':   'ml_gradient_boost',
            'warnings':          [],
            'uncertainty_reasons': [],
            'csv_ppm2_used':     None,
        }
    except Exception as exc:
        logger.warning('ML prediction failed: %s', exc)
        return None


def is_available() -> bool:
    return _load_model() is not None
