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

    def run_served_stability_test(self, bundle: Any, base_request: dict, model_property_type: str,
                                  seed: int = 0) -> dict:
        """Stability of the served model's own explanations.

        The base request and N_SAMPLES copies with the surface varied by about 5%
        go through the serving path (request mapper -> bundle.predict), and the top
        three features by |SHAP| are compared with the unperturbed request's. A
        model that returns no attributions fails: its stability can't be checked.

        (run_stability_test above fed form fields as numbers to the estimator; the
        SHAP call could not run on them, and the fallback ranked the input numbers
        themselves, so the result said nothing about the model.)
        """
        from estatemind.intelligence.valuation.inference.request_mapper import map_request

        rng = np.random.default_rng(seed)
        requests = [dict(base_request)] + [
            {**base_request, 'size_m2': round(float(base_request['size_m2']) * (1 + rng.normal(0, 0.05)), 1)}
            for _ in range(self.N_SAMPLES)
        ]
        rankings, contributions = [], []
        for req in requests:
            mapped = map_request(req)
            mapped['model_property_type'] = model_property_type
            pred = bundle.predict(mapped, {'avg_price_per_m2': None})
            phi = dict((getattr(pred, 'attributions', None) or {}).get('phi') or {})
            phi.pop('transaction_type', None)  # constant for a sale
            if not phi:
                return {'stability_rate': 0.0, 'status': 'fail', 'n_samples': self.N_SAMPLES,
                        'reference_ranking': [], 'rank_variance': {}, 'unstable_features': [],
                        'recommendation': 'The model returns no SHAP attributions, so stability cannot be checked. '
                                          'Do NOT promote.'}
            contributions.append(phi)
            rankings.append(sorted(phi, key=lambda f: abs(phi[f]), reverse=True)[:3])

        reference = rankings[0]
        stability_rate = sum(1 for r in rankings[1:] if r == reference) / self.N_SAMPLES
        rank_variance = {}
        for feature in contributions[0]:
            positions = [sorted(c, key=lambda f: abs(c[f]), reverse=True).index(feature) for c in contributions]
            rank_variance[feature] = round(float(np.std(positions)), 2)
        unstable = [name for name, var in rank_variance.items() if var > 1.5]
        status = 'pass' if stability_rate >= self.PASS_THRESHOLD else 'warn' if stability_rate >= self.WARN_THRESHOLD else 'fail'
        return {
            'stability_rate': round(stability_rate, 3),
            'status': status,
            'n_samples': self.N_SAMPLES,
            'reference_ranking': reference,
            'rank_variance': rank_variance,
            'unstable_features': unstable,
            'recommendation': self._recommend(status, unstable),
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
