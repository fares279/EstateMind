from __future__ import annotations

from typing import Any

import numpy as np


class SHAPStabilityTester:
    """Checks whether a model's explanations are stable under minor perturbations.

    Stability rule (revised 2026-09-29, applies to every promotion): a perturbed
    request is stable when its top three features by |SHAP| are the same *set* as
    the unperturbed request's, in any order. Requiring the same order counted
    correlated features trading places as instability: surface, size x local price
    and local price all move with the surface, so a 5% change in surface reorders
    them without the model relying on anything different. A different feature
    entering the top three is still counted. The exact-order rate is reported too,
    for information. The thresholds were not changed with the rule.
    """

    N_SAMPLES = 100
    PASS_THRESHOLD = 0.90
    WARN_THRESHOLD = 0.75

    def run_served_stability_test(self, bundle: Any, base_request: dict, model_property_type: str,
                                  seed: int = 0) -> dict:
        """Stability of the served model's own explanations.

        The base request and N_SAMPLES copies with the surface varied by about 5%
        go through the serving path (request mapper -> bundle.predict), and the top
        three features by |SHAP| are compared with the unperturbed request's. A
        model that returns no attributions fails: its stability can't be checked.

        (The previous run_stability_test fed form fields as numbers to the estimator;
        the SHAP call could not run on them, and the fallback ranked the input
        numbers themselves, so the result said nothing about the model.)
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
                return {'stability_rate': 0.0, 'exact_order_rate': 0.0, 'status': 'fail',
                        'n_samples': self.N_SAMPLES,
                        'reference_ranking': [], 'rank_variance': {}, 'unstable_features': [],
                        'recommendation': 'The model returns no SHAP attributions, so stability cannot be checked. '
                                          'Do NOT promote.'}
            contributions.append(phi)
            rankings.append(sorted(phi, key=lambda f: abs(phi[f]), reverse=True)[:3])

        reference = rankings[0]
        stability_rate = sum(1 for r in rankings[1:] if set(r) == set(reference)) / self.N_SAMPLES
        exact_order_rate = sum(1 for r in rankings[1:] if r == reference) / self.N_SAMPLES
        rank_variance = {}
        for feature in contributions[0]:
            positions = [sorted(c, key=lambda f: abs(c[f]), reverse=True).index(feature) for c in contributions]
            rank_variance[feature] = round(float(np.std(positions)), 2)
        unstable = [name for name, var in rank_variance.items() if var > 1.5]
        status = 'pass' if stability_rate >= self.PASS_THRESHOLD else 'warn' if stability_rate >= self.WARN_THRESHOLD else 'fail'
        return {
            'stability_rate': round(stability_rate, 3),
            'exact_order_rate': round(exact_order_rate, 3),
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
