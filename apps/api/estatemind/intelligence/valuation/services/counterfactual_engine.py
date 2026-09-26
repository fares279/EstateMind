from __future__ import annotations

from typing import Any, Callable

import numpy as np


class CounterfactualEngine:
    """Generate local counterfactuals for mutable property features."""

    TARGET_CHANGE_PCT = 0.10
    MAX_ITERATIONS = 40
    MUTABLE_FEATURES = ['condition_score_image', 'condition', 'sqm', 'size_m2', 'bedrooms', 'bathrooms']

    def generate(self, model: Any, base_features: dict, base_prediction: float, predict_fn: Callable[[dict], float] | None = None) -> list[dict]:
        target = float(base_prediction) * (1 + self.TARGET_CHANGE_PCT)
        counterfactuals = []
        for feature in self.MUTABLE_FEATURES:
            result = self._search_counterfactual(model, base_features, base_prediction, target, feature, predict_fn=predict_fn)
            if result:
                counterfactuals.append(result)
        return sorted(counterfactuals, key=lambda item: abs(item['delta_tnd']), reverse=True)[:3]

    def _search_counterfactual(self, model: Any, base: dict, base_pred: float, target: float, feature: str, predict_fn: Callable[[dict], float] | None = None) -> dict | None:
        original_val = base.get(feature)
        if original_val is None:
            return None
        if not isinstance(original_val, (int, float)):
            return None

        lo, hi = float(original_val) * 0.5, float(original_val) * 2.0
        best = None
        for _ in range(self.MAX_ITERATIONS):
            mid = (lo + hi) / 2
            test_features = {**base, feature: mid}
            pred = self._predict(model, test_features, predict_fn=predict_fn)
            if pred is None:
                return None
            if abs(pred - target) / max(target, 1.0) < 0.02:
                delta = pred - base_pred
                best = {
                    'feature': feature,
                    'original_value': original_val,
                    'new_value': round(mid, 2),
                    'new_prediction': round(pred),
                    'delta_tnd': round(delta),
                    'delta_pct': round((delta / max(base_pred, 1.0)) * 100, 1),
                    'description': self._describe(feature, original_val, mid, delta, base_pred),
                }
                break
            if pred < target:
                lo = mid
            else:
                hi = mid
        return best

    def _predict(self, model: Any, features: dict, predict_fn: Callable[[dict], float] | None = None) -> float | None:
        try:
            if predict_fn is not None:
                return float(predict_fn(features))
            if hasattr(model, 'predict'):
                prediction = model.predict([list(features.values())])
                if isinstance(prediction, (list, tuple, np.ndarray)):
                    return float(prediction[0])
                return float(prediction)
        except Exception:
            return None
        return None

    def _describe(self, feature: str, original: float, new_value: float, delta: float, base_prediction: float) -> str:
        return (
            f"Changing {feature} from {round(original, 2)} to {round(new_value, 2)} "
            f"would shift the valuation by {round(delta):,} TND (+{round((delta / max(base_prediction, 1.0)) * 100, 1)}%)."
        )
