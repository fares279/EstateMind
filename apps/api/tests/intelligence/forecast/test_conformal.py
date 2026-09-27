import numpy as np
from django.test import SimpleTestCase

from estatemind.intelligence.forecast.services.conformal_predictor import ConformalPredictor


class ConformalCoverageTests(SimpleTestCase):
    """The split-conformal guarantee holds when future errors resemble past ones."""

    def test_iid_errors_reach_nominal_coverage(self):
        # The guarantee is marginal: coverage >= 90% on average over calibration sets.
        rng = np.random.default_rng(0)
        future = rng.normal(0, 10, 20_000)
        coverages = []
        for _ in range(100):
            cp = ConformalPredictor(coverage=0.90)
            cp.calibrate(rng.normal(0, 10, 200).tolist())
            coverages.append(float(np.mean(np.abs(future) <= cp.quantile_for())))
        self.assertGreaterEqual(np.mean(coverages), 0.895)
        self.assertLessEqual(np.mean(coverages), 0.92)

    def test_rank_is_ceil_n_plus_one_times_coverage(self):
        cp = ConformalPredictor(coverage=0.90)
        cp.calibrate(list(range(1, 11)))          # n=10 -> k=ceil(11*0.9)=10 -> 10th smallest
        self.assertEqual(cp.quantile_for(), 10.0)
        cp.calibrate(list(range(1, 101)))         # n=100 -> k=91
        self.assertEqual(cp.quantile_for(), 91.0)

    def test_per_horizon_widths_follow_growing_error(self):
        rng = np.random.default_rng(1)
        residuals, horizons = [], []
        for _ in range(60):
            for h in range(1, 13):
                residuals.append(rng.normal(0, h))   # error grows with horizon
                horizons.append(h)
        cp = ConformalPredictor(coverage=0.90)
        cp.calibrate(residuals, horizons=horizons)
        self.assertLess(cp.quantile_for(1), cp.quantile_for(12))
        for h in (1, 12):
            future = rng.normal(0, h, 20_000)
            self.assertAlmostEqual(float(np.mean(np.abs(future) <= cp.quantile_for(h))), 0.90, delta=0.03)
        # the pooled width badly under-covers the long horizon
        pooled = float(np.mean(np.abs(rng.normal(0, 12, 20_000)) <= cp.quantile_for()))
        self.assertLess(pooled, 0.80)

    def test_interval_uses_horizon_width(self):
        cp = ConformalPredictor(coverage=0.90)
        cp.calibrate([1.0] * 30 + [5.0] * 30, horizons=[1] * 30 + [12] * 30)
        self.assertEqual(cp.predict_interval(100, horizon=1)['high'], 101.0)
        self.assertEqual(cp.predict_interval(100, horizon=12)['high'], 105.0)
