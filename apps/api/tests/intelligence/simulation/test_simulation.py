import json
import uuid
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from estatemind.intelligence.simulation.engine.simulator import TunisiaRealEstateSimulator
from estatemind.intelligence.simulation.models import SimulationRun


def _run(months=6, seed=1, scenario='baseline'):
    run_id = str(uuid.uuid4())
    SimulationRun.objects.create(run_id=run_id, scenario_name=scenario, agent_scale='tiny', num_months=months,
                                 status=SimulationRun.STATUS_PENDING)
    TunisiaRealEstateSimulator(run_id=run_id, scenario_name=scenario, num_months=months, agent_scale='tiny',
                               seed=seed, policy_overrides={}).run()
    return SimulationRun.objects.get(run_id=run_id)


class SimulatorEngineTests(TestCase):
    def test_run_completes_with_one_state_per_month(self):
        run = _run(months=6)
        self.assertEqual((run.status, run.current_month), (SimulationRun.STATUS_COMPLETE, 6))
        self.assertEqual(len(run.monthly_states), 6)
        self.assertTrue(all(s['avg_price'] > 0 for s in run.monthly_states))

    def test_same_seed_is_reproducible(self):
        a, b = _run(seed=7), _run(seed=7)
        self.assertEqual([s['avg_price'] for s in a.monthly_states], [s['avg_price'] for s in b.monthly_states])


class SimulationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _start(self, body):
        return self.client.post('/api/simulate/start/', data=json.dumps(body), content_type='application/json')

    def test_scenarios_are_listed(self):
        scenarios = self.client.get('/api/simulate/scenarios/').json()['scenarios']
        self.assertIn('baseline', {s['id'] for s in scenarios})
        self.assertTrue(all(s['label'] for s in scenarios))

    def test_start_validation(self):
        self.assertEqual(self._start({'scenario_name': 'nope'}).status_code, 400)
        self.assertEqual(self._start({'num_months': 'twelve'}).status_code, 400)
        self.assertEqual(self._start({'policy_overrides': [1, 2]}).status_code, 400)
        bad_json = self.client.post('/api/simulate/start/', data='{', content_type='application/json')
        self.assertEqual(bad_json.status_code, 400)

    @mock.patch('estatemind.intelligence.simulation.views.threading.Thread')
    def test_start_clamps_months_and_filters_overrides(self, thread):
        response = self._start({'scenario_name': 'baseline', 'num_months': 500,
                                'policy_overrides': {'bct_rate': '0.09', 'rm -rf': 1, 'demand_multiplier': 'x'}})
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body['num_months'], 60)
        self.assertEqual(body['policy_overrides'], {'bct_rate': 0.09})
        self.assertTrue(SimulationRun.objects.filter(run_id=body['run_id']).exists())
        thread.return_value.start.assert_called_once()

    def test_results_endpoints_for_a_finished_run(self):
        run = _run(months=6)
        detail = self.client.get(f'/api/simulate/runs/{run.run_id}/').json()
        self.assertEqual((detail['status'], detail['progress_pct']), (SimulationRun.STATUS_COMPLETE, 100.0))
        self.assertEqual(len(self.client.get(f'/api/simulate/runs/{run.run_id}/timeseries/').json()['months']), 6)
        other = _run(months=6, seed=2)
        compare = self.client.get('/api/simulate/compare/', {'run_a': run.run_id, 'run_b': other.run_id}).json()
        self.assertIn('price_change_pct', compare['run_a']['summary'])

    def test_unknown_run_is_404(self):
        self.assertEqual(self.client.get(f'/api/simulate/runs/{uuid.uuid4()}/').status_code, 404)
