"""
Celery tasks for market simulator operations.

Tasks:
- run_ensemble_task: Execute ensemble in background
- validate_scenario_task: Pre-submission validation
- test_rl_policy_task: Test RL policy across scenarios
- calibrate_agents_task: Inverse RL calibration
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
    """
    Test RL investment policy across scenarios.
    
    Called by: Admin interface or scheduled RL validation workflow
    """
    
    # Not implemented: RLPolicySimulationTester._run_with_strategy does not run
    # the simulator (it samples returns from fixed distributions), so any
    # ranking or DEPLOY/REJECT assessment it produced would be fabricated.
    # Previously this task returned a hard-coded 'DEPLOY'.
    logger.warning('test_rl_policy_task called, but RL policy backtesting is not implemented')
    return {
        'status': 'not_implemented',
        'reason': 'RL policy backtesting inside the simulator is not implemented; '
                  'no assessment is produced.',
        'scenarios_requested': len(scenarios or []),
    }


@shared_task(bind=True)
def calibrate_agents_task(self, agent_types=['buyer', 'developer', 'speculator']):
    """
    Run inverse RL agent calibration.
    
    Called by: Scheduled job (e.g., weekly) or admin command
    
    Workflow:
    1. Extract behavioral data from market history
    2. Calibrate reward weights via MLE
    3. Validate calibration quality
    4. Persist AgentCalibrationProfile
    5. Update is_active flag
    """
    
    # Not implemented: AgentRewardCalibrator's likelihood does not depend on the
    # weights and validate_calibration returns fixed errors, so persisting an
    # AgentCalibrationProfile from them would record fabricated quality metrics.
    # (The previous body also failed on import: it imported `.calibration`
    # instead of `.services.calibration`.)
    logger.warning('calibrate_agents_task called, but agent calibration is not implemented')
    return {
        'status': 'not_implemented',
        'reason': 'Inverse-RL agent calibration is not implemented; no profile is created.',
        'agent_types_requested': list(agent_types),
    }
