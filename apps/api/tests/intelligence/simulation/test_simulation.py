import json
import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from estatemind.intelligence.simulation.engine.simulator import TunisiaRealEstateSimulator
from estatemind.intelligence.simulation.models import SimulationRun


def _run(months=6, seed=1, scenario='baseline', owner=None):
    run_id = str(uuid.uuid4())
    SimulationRun.objects.create(run_id=run_id, scenario_name=scenario, agent_scale='tiny', num_months=months,
                                 status=SimulationRun.STATUS_PENDING, owner=owner)
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


def _user(email, **extra):
    return get_user_model().objects.create_user(email=email, password='pw12345!x', full_name='U', **extra)


def _login(client, user):
    # these views read the JWT header themselves (plain Django views)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')


class SimulationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = _user('sim@example.com')
        _login(self.client, self.user)

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
        self.assertEqual(SimulationRun.objects.get(run_id=body['run_id']).owner, self.user)
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


@mock.patch('estatemind.intelligence.simulation.views.threading.Thread')
class SimulationPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner, self.other = _user('owner@example.com'), _user('other@example.com')
        self.staff = _user('staff@example.com', is_staff=True)
        self.run = _run(owner=self.owner)
        self.orphan = _run(owner=None)

    def _delete(self, run):
        return self.client.delete(f'/api/simulate/runs/{run.run_id}/')

    def test_start_requires_login(self, _thread):
        response = self.client.post('/api/simulate/start/', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.assertIn('Log in', response.json()['error'])

    def test_bad_token_is_treated_as_anonymous(self, _thread):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-token')
        self.assertEqual(self.client.post('/api/simulate/start/', data='{}',
                                          content_type='application/json').status_code, 401)

    def test_reads_stay_public(self, _thread):
        self.assertEqual(self.client.get(f'/api/simulate/runs/{self.run.run_id}/').status_code, 200)
        self.assertEqual(self.client.get('/api/simulate/runs/').status_code, 200)

    def test_delete_rules(self, _thread):
        self.assertEqual(self._delete(self.run).status_code, 401)              # anonymous
        _login(self.client, self.other)
        self.assertEqual(self._delete(self.run).status_code, 403)              # someone else's run
        self.assertEqual(self._delete(self.orphan).status_code, 403)           # ownerless: staff only
        _login(self.client, self.owner)
        self.assertEqual(self._delete(self.run).status_code, 200)              # owner
        _login(self.client, self.staff)
        self.assertEqual(self._delete(self.orphan).status_code, 200)           # staff
        self.assertFalse(SimulationRun.objects.exists())

    def test_list_says_who_can_delete(self, _thread):
        _login(self.client, self.owner)
        flags = {r['run_id']: r['can_delete'] for r in self.client.get('/api/simulate/runs/').json()['runs']}
        self.assertEqual(flags, {str(self.run.run_id): True, str(self.orphan.run_id): False})


class SimulationBackendTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        _login(self.client, _user('backend@example.com'))

    def _start(self):
        return self.client.post('/api/simulate/start/', data=json.dumps({'scenario_name': 'baseline', 'num_months': 6}),
                                content_type='application/json')

    @mock.patch('estatemind.intelligence.simulation.views.threading.Thread')
    @mock.patch('estatemind.intelligence.simulation.tasks.run_simulation_task.apply_async')
    def test_celery_backend_queues_the_run(self, apply_async, thread):
        with self.settings(SIMULATION_BACKEND='celery'):
            response = self._start()
        self.assertEqual(response.status_code, 201)
        args = apply_async.call_args.kwargs['args']
        self.assertEqual((args[0], args[1], args[2]), (response.json()['run_id'], 'baseline', 6))
        thread.assert_not_called()

    @mock.patch('estatemind.intelligence.simulation.views.threading.Thread')
    @mock.patch('estatemind.intelligence.simulation.tasks.run_simulation_task.apply_async',
                side_effect=ConnectionError('broker down'))
    def test_unreachable_broker_falls_back_to_a_thread(self, _apply_async, thread):
        with self.settings(SIMULATION_BACKEND='celery'):
            self.assertEqual(self._start().status_code, 201)
        thread.return_value.start.assert_called_once()

    def test_task_runs_the_simulation(self):
        from estatemind.intelligence.simulation.tasks import run_simulation_task
        run_id = str(uuid.uuid4())
        SimulationRun.objects.create(run_id=run_id, scenario_name='baseline', agent_scale='tiny', num_months=3,
                                     status=SimulationRun.STATUS_PENDING)
        run_simulation_task(run_id, 'baseline', 3, 'tiny', 1, {})
        self.assertEqual(SimulationRun.objects.get(run_id=run_id).status, SimulationRun.STATUS_COMPLETE)
