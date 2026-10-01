"""
Celery tasks for market simulator operations.

Tasks:
- run_ensemble_task: Execute ensemble in background
- validate_scenario_task: Pre-submission validation
- test_rl_policy_task: Strategy backtest (buy now vs wait) inside the simulator
- calibrate_agents_task: Calibrate starting price levels to real listings
"""

import logging
from celery import shared_task
from django.utils import timezone

from .models import SimulationRun
from .services.validation import ScenarioValidator
from .services.ensemble import EnsembleSimulator, StochasticTester

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_ensemble_task(self, simulation_run_id):
    """
    Execute an ensemble simulation in background.
    
    Flow:
    1. Load SimulationRun job
    2. Run ensemble simulations (N runs in parallel)
    3. Execute stochastic tests
    4. Aggregate results
    5. Persist to database
    6. Update status
    """
    
    try:
        job = SimulationRun.objects.get(run_id=simulation_run_id)
        job.status = SimulationRun.STATUS_RUNNING
        job.started_at = timezone.now()
        job.save()
        
        logger.info(f'Starting ensemble task for job {simulation_run_id}')
        
        # Initialize ensemble (uses real simulator by default)
        ensemble = EnsembleSimulator(max_workers=4)
        
        # Run ensemble - REAL execution
        try:
            ensemble_output = ensemble.run_ensemble(
                scenario=job.scenario_config,
                n_runs=job.n_runs,
                n_agents=job.agent_scale,  # scale preset ('tiny', 'small', ...)
            )
            logger.info(f'Ensemble completed: {ensemble_output["ensemble_size"]} runs')
        except Exception as e:
            logger.exception('Ensemble execution failed')
            ensemble_output = {
                'ensemble_size': 0,
                'error': str(e),
                'monthly_price_bands': {},
                'probabilities': {},
            }
        
        # Run stochastic tests
        try:
            tester = StochasticTester(ensemble.simulator)
            repro_test = tester.test_reproducibility(
                scenario=job.scenario_config,
                n_agents='medium'
            )
            variance_test = tester.test_variance(
                scenario=job.scenario_config,
                n_agents='medium',
                n_runs=5,
            )
            tests_result = {
                'reproducibility': repro_test,
                'variance': variance_test,
                'historical_calibration': {'status': 'SKIPPED'},  # Requires historical data
            }
            logger.info(f'Stochastic tests: reproducibility={repro_test.get("passed")}, variance={variance_test.get("assessment")}')
        except Exception as e:
            logger.exception('Stochastic tests failed')
            tests_result = {
                'reproducibility': {'passed': False, 'error': str(e)},
                'variance': {'passed': False, 'error': str(e)},
                'historical_calibration': {'status': 'ERROR'},
            }
        
        # Save results
        job.ensemble_output = ensemble_output
        job.stochastic_tests = tests_result
        job.reproducibility_passed = tests_result['reproducibility']['passed']
        job.calibration_quality = tests_result['variance']['assessment']
        job.status = SimulationRun.STATUS_COMPLETE
        job.completed_at = timezone.now()
        job.save()
        
        logger.info(f'Completed ensemble task for job {simulation_run_id}')
        return {
            'status': 'success',
            'job_id': str(simulation_run_id),
            'ensemble_output': ensemble_output,
        }
    
    except Exception as e:
        logger.exception(f'Ensemble task failed for job {simulation_run_id}')
        
        # Retry with exponential backoff
        try:
            job = SimulationRun.objects.get(run_id=simulation_run_id)
            job.status = SimulationRun.STATUS_ERROR
            job.error_message = str(e)
            job.save()
        except:
            pass
        
        # Retry after 60s, 120s, 300s
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True)
def validate_scenario_task(self, scenario_config, validation_mode='strict'):
    """
    Validate scenario parameters (lightweight task).
    
    Used for pre-submission validation before enqueueing
    expensive ensemble task.
    """
    
    try:
        from .services.validation import ValidationMode
        
        validator = ScenarioValidator(
            mode=ValidationMode.STRICT if validation_mode == 'strict'
            else ValidationMode.EXPLORATORY
        )
        
        result = validator.validate(scenario_config)
        
        return result
    
    except Exception as e:
        logger.exception('Scenario validation failed')
        return {
            'error': str(e),
            'can_proceed': False
        }


@shared_task(bind=True)
def test_rl_policy_task(self, scenarios, n_runs_per_scenario=20):
    """Strategy backtest inside the simulator: buy now vs wait 6 or 12 months, scored on
    price paths of the agent-based model (services/strategy_backtest.py). Results are
    simulated outcomes, labelled as such. (The RL policy tester this name comes from
    sampled returns from fixed distributions, so it is not used.)"""
    from .services.strategy_backtest import backtest

    try:
        return backtest(scenarios, n_runs=n_runs_per_scenario)
    except ValueError as e:
        return {'status': 'invalid', 'reason': str(e)}


@shared_task(bind=True)
def calibrate_agents_task(self, agent_types=None):
    """Calibrate the simulator's starting price levels to real sale listings and write
    data/simulator_calibration.json (engine/calibration.py); returns the error report.

    Agent reward weights are not calibrated: inverse RL needs observed transactions
    (who bought what, when, at what price), and the data holds asking prices only.
    """
    from .engine.calibration import CALIBRATION_PATH, calibrate_and_save

    calibration = calibrate_and_save()
    return {
        'status': 'completed',
        'calibrated': 'starting price levels',
        'not_calibrated': {
            'agent_types': list(agent_types or []),
            'reason': 'Agent behaviour (reward weights) needs transaction data; only asking prices exist.',
        },
        'report': calibration['report'],
        'zones': len(calibration['zones']),
        'path': str(CALIBRATION_PATH),
    }


@shared_task(name='estatemind.intelligence.simulation.tasks.run_simulation_task')
def run_simulation_task(run_id, scenario_name, num_months, agent_scale, seed=None, policy_overrides=None):
    """One simulation run on a Celery worker (SIMULATION_BACKEND=celery), so runs don't
    compete with web requests. The simulator records completion or failure on the run."""
    from .engine.simulator import TunisiaRealEstateSimulator

    TunisiaRealEstateSimulator(
        run_id=run_id,
        scenario_name=scenario_name,
        num_months=num_months,
        agent_scale=agent_scale,
        seed=seed,
        policy_overrides=policy_overrides or {},
    ).run()
    return {'run_id': run_id}
