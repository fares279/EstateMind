"""Monthly rent per m² from the model trained by ml.investor.train_rent_model, which
beat the delegation/governorate medians on held-out real rental listings. Absent
artifact: predict() returns None and callers use the medians (market_rent.py)."""
from __future__ import annotations

import logging
import math
from functools import lru_cache

from config.paths import ARTIFACTS_DIR

logger = logging.getLogger(__name__)

MODEL_PATH = ARTIFACTS_DIR / 'investor' / 'rent_ppm_catboost.joblib'
REPORT_PATH = ARTIFACTS_DIR / 'investor' / 'rent_ppm_report.json'
RENTED_TYPES = ('apartment', 'house')


@lru_cache(maxsize=1)
def _model():
    if not MODEL_PATH.exists():
        return None
    try:
        import joblib
        return joblib.load(MODEL_PATH)
    except Exception as e:  # a broken artifact must not take the investor pages down
        logger.warning('Rent model %s could not be loaded: %s', MODEL_PATH, e)
        return None


def predict(property_type: str, delegation: str, governorate: str, surface_m2: float | None = None,
            rooms=None, bedrooms=None, bathrooms=None) -> float | None:
    """Monthly rent per m² in TND, or None (no model, or a type that is not rented out)."""
    model = _model()
    if model is None or property_type not in RENTED_TYPES:
        return None
    import pandas as pd

    from ml.investor.train_rent_model import frame
    row = pd.DataFrame([{'property_type': property_type, 'delegation': delegation, 'governorate': governorate,
                         'area_sqm': surface_m2, 'rooms': rooms, 'bedrooms': bedrooms, 'bathrooms': bathrooms}])
    value = math.exp(float(model.predict(frame(row))[0]))
    return value if math.isfinite(value) and value > 0 else None
