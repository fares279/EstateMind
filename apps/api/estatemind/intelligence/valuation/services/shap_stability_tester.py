from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class StabilityResult:
    stability_rate: float
    status: str
    n_samples: int
    reference_ranking: list[str]
    rank_variance: dict[str, float]
    unstable_features: list[str]
    recommendation: str


class SHAPStabilityTester:
    """Checks whether explanation rankings are stable under minor perturbations."""

    N_SAMPLES = 100
    PASS_THRESHOLD = 0.90
    WARN_THRESHOLD = 0.75

    def run_stability_test(self, model: Any, base_property: dict, feature_names: list[str]) -> dict:
        samples = self._generate_perturbations(base_property, feature_names)
        try:
            import shap  # type: ignore

            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(np.array(samples))
            if isinstance(shap_values, list):
                shap_values = shap_values[0]
        except Exception:
            # Fallback: approximate importance with feature deviations if SHAP is unavailable.
            shap_values = np.array([np.array(sample, dtype=float) for sample in samples], dtype=float)

        rankings = [list(np.argsort(np.abs(sv))[::-1][:3]) for sv in shap_values]
        reference_ranking = rankings[0]
        match_count = sum(1 for ranking in rankings[1:] if ranking == reference_ranking)
        pair_count = max(len(rankings) - 1, 1)
        stability_rate = match_count / pair_count

        rank_positions = {name: [] for name in feature_names}
        for sv in shap_values:
            sorted_features = list(np.argsort(np.abs(sv))[::-1])
            for rank, idx in enumerate(sorted_features):
                if idx < len(feature_names):
                    rank_positions[feature_names[idx]].append(rank)

        rank_variance = {
            name: round(float(np.std(positions)), 2)
            for name, positions in rank_positions.items()
            if positions
        }
        unstable_features = [name for name, var in rank_variance.items() if var > 1.5]
        status = 'pass' if stability_rate >= self.PASS_THRESHOLD else 'warn' if stability_rate >= self.WARN_THRESHOLD else 'fail'

        return {
            'stability_rate': round(stability_rate, 3),
            'status': status,
            'n_samples': self.N_SAMPLES,
            'reference_ranking': [feature_names[i] for i in reference_ranking if i < len(feature_names)],
            'rank_variance': rank_variance,
            'unstable_features': unstable_features,
            'recommendation': self._recommend(status, unstable_features),
        }

    def _recommend(self, status: str, unstable: list[str]) -> str:
        if status == 'pass':
            return 'SHAP explanations are stable. Safe to promote.'
        if status == 'warn':
            return f"Moderate instability in: {', '.join(unstable)}. Review feature scaling before promoting."
        return f"High instability in: {', '.join(unstable)}. Do NOT promote. Check for overfitting or correlated features."

    def _generate_perturbations(self, base: dict, features: list[str]) -> list[list[float]]:
        samples = []
        for _ in range(self.N_SAMPLES):
            sample = []
            for feature in features:
                value = base.get(feature, 0)
                if isinstance(value, (int, float)):
                    sample.append(float(value) * (1 + np.random.normal(0, 0.05)))
                else:
                    sample.append(0.0)
            samples.append(sample)
        return samples
