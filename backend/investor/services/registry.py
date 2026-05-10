"""
Loads all 7 investor ML models from investor/outputs/models/.
Models directory lives outside the Django project at:
  <repo_root>/investor/outputs/models/
"""
from pathlib import Path
from functools import lru_cache
import json
import logging

logger = logging.getLogger(__name__)

try:
    import joblib
    _JOBLIB = True
except ImportError:
    _JOBLIB = False

try:
    import xgboost as xgb
    _XGB = True
except ImportError:
    xgb = None
    _XGB = False

# registry.py → services/ → investor/ → backend/ → EstateMind/ → EstateMind (root)
_ROOT = Path(__file__).resolve().parents[4]
MODELS_DIR = _ROOT / 'investor' / 'outputs' / 'models'

_MODEL_FILES = {
    'undervaluation_detector': (
        MODELS_DIR / 'model1_undervaluation_20260504_200340.pkl',
        MODELS_DIR / 'model1_undervaluation_20260504_200340.json',
    ),
    'rental_yield':            (MODELS_DIR / 'rental_yield_model.pkl',),
    'buy_wait_classifier':     (MODELS_DIR / 'buy_wait_classifier.pkl',),
    'opportunity_score_engine':(MODELS_DIR / 'opportunity_score_engine.pkl',),
    'investment_grade_classifier': (MODELS_DIR / 'investment_grade_classifier.pkl',),
    'irr_predictor':           (MODELS_DIR / 'irr_predictor.pkl',),
    'portfolio_risk_scorer':   (MODELS_DIR / 'portfolio_risk_scorer.pkl',),
}

_FEATURE_FILES = {
    'undervaluation_detector': MODELS_DIR / 'feature_names.json',
    'rental_yield':            MODELS_DIR / 'rental_yield_features.json',
    'buy_wait_classifier':     MODELS_DIR / 'buy_wait_classifier_features.json',
    'opportunity_score_engine':MODELS_DIR / 'opportunity_score_engine_features.json',
    'investment_grade_classifier': MODELS_DIR / 'investment_grade_classifier_features.json',
    'irr_predictor':           MODELS_DIR / 'irr_predictor_features.json',
    'portfolio_risk_scorer':   MODELS_DIR / 'portfolio_risk_scorer_features.json',
}


def _load_model(paths):
    if not _JOBLIB:
        return None
    for path in paths:
        if not path.exists():
            continue
        try:
            if path.suffix == '.json' and _XGB:
                b = xgb.Booster()
                b.load_model(str(path))
                return b
            return joblib.load(path)
        except Exception as e:
            logger.warning("Failed to load %s: %s", path, e)
    return None


def _load_features(path: Path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            return data.get('features') or data.get('feature_names') or []
        return data
    except Exception:
        return []


class _Registry:
    def __init__(self):
        self._models = {}
        self._features = {}
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        for name, paths in _MODEL_FILES.items():
            self._models[name] = _load_model(paths)
            self._features[name] = _load_features(_FEATURE_FILES.get(name, Path('_')))
            status = 'OK' if self._models[name] is not None else 'MISSING'
            logger.info("Investor model %-35s %s", name, status)
        self._loaded = True

    def model(self, name: str):
        self._ensure_loaded()
        return self._models.get(name)

    def features(self, name: str):
        self._ensure_loaded()
        return self._features.get(name, [])

    def is_available(self, name: str) -> bool:
        self._ensure_loaded()
        return self._models.get(name) is not None

    def available(self):
        self._ensure_loaded()
        return [k for k, v in self._models.items() if v is not None]


REGISTRY = _Registry()
