from django.test import SimpleTestCase

from estatemind.intelligence.simulation.engine.calibration import build_calibration
from estatemind.intelligence.simulation.engine.config import DELEGATION_DATA
from estatemind.intelligence.simulation.services.strategy_backtest import backtest


def _zone(gov, avg):
    return {'avg_price': avg, 'governorate': gov}


class CalibrationTests(SimpleTestCase):
    def setUp(self):
        # three delegations of G with listings at 0.5x the benchmark, one without listings
        self.index = {(f'D{i}', 'apartment'): _zone('G', 2000.0) for i in range(4)}
        self.medians = {(f'D{i}', 'G', 'apartment'): (1000.0, 8) for i in range(3)}

    def test_zones_with_listings_start_from_their_median(self):
        zones = build_calibration(self.index, self.medians)['zones']
        self.assertEqual(zones['D0|apartment'], {'multiplier': 0.5, 'basis': 'listings', 'listings': 8})

    def test_other_zones_take_the_governorate_ratio_when_it_helps(self):
        cal = build_calibration(self.index, self.medians)
        self.assertEqual(cal['zones']['D3|apartment']['multiplier'], 0.5)
        self.assertEqual(cal['zones']['D3|apartment']['basis'], 'governorate_ratio')
        report = cal['report']['apartment']
        self.assertEqual(report['benchmark_median_ape'], 1.0)
        self.assertEqual(report['corrected_median_ape_leave_one_out'], 0.0)

    def test_correction_is_skipped_when_it_does_not_beat_the_benchmark(self):
        # ratios all over the place: leave-one-out correction is worse than the raw benchmark
        medians = {('D0', 'G', 'apartment'): (200.0, 8), ('D1', 'G', 'apartment'): (2100.0, 8),
                   ('D2', 'G', 'apartment'): (9000.0, 8)}
        zones = build_calibration(self.index, medians)['zones']
        self.assertEqual(zones['D3|apartment'], {'multiplier': 1.0, 'basis': 'benchmark', 'listings': 0})

    def test_coastal_flag_follows_the_coastline(self):
        coastal = {d['delegation']: d['is_coastal'] for d in DELEGATION_DATA}
        self.assertTrue(coastal['Hammamet'])
        self.assertFalse(coastal['Béja Nord'])  # Béja was a "coastal governorate"


class StrategyBacktestTests(SimpleTestCase):
    def test_runs_the_simulator_and_labels_results_simulated(self):
        result = backtest(['baseline', 'interest_rate_hike'], n_runs=2, agent_scale='tiny')
        self.assertEqual(result['kind'], 'simulated')
        hike = result['scenarios']['interest_rate_hike']
        self.assertEqual(hike['runs'], 2)
        self.assertLessEqual(hike['buy_now_hold']['p05_pct'], hike['buy_now_hold']['p95_pct'])
        # a rate hike lowers simulated prices relative to easing
        easing = backtest(['monetary_easing'], n_runs=2, agent_scale='tiny')['scenarios']['monetary_easing']
        self.assertLess(hike['buy_now_hold']['mean_pct'], easing['buy_now_hold']['mean_pct'])

    def test_unknown_scenario_is_rejected(self):
        with self.assertRaises(ValueError):
            backtest(['no_such_scenario'], n_runs=1)
