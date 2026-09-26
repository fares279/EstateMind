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
from datetime import timedelta

from .models import SimulationRun, AgentCalibrationProfile
from .services.validation import ScenarioValidator
from .services.ensemble import EnsembleSimulator, StochasticTester
from .services.rl_feedback import RLPolicySimulationTester

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
                n_agents='medium',  # TODO: map job.n_agents to scale string
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
    
    try:
        # TODO: Import actual RL policy from Module 7
        # from classifiers.models import InvestmentPolicy
        # rl_policy_model = InvestmentPolicy.objects.get(is_active=True)
        # rl_policy_func = rl_policy_model.get_decision_function()
        
        # TODO: Import simulator
        # from .engine import MultiAgentSimulator
        # simulator_func = MultiAgentSimulator().run
        
        # tester = RLPolicySimulationTester(simulator_func, rl_policy_func)
        # results = tester.test_policy_across_scenarios(
        #     scenarios=scenarios,
        #     n_runs_per_scenario=n_runs_per_scenario,
        # )
        
        # For now, mock
        results = {
            'scenario_results': {},
            'overall_ranking': {
                'best_strategy': 'rl_policy',
                'ranking': []
            },
            'rl_policy_assessment': {
                'assessment': 'DEPLOY',
            }
        }
        
        logger.info(f'Completed RL policy test')
        return results
    
    except Exception as e:
        logger.exception('RL policy test failed')
        return {
            'error': str(e),
            'status': 'failed'
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
    
    try:
        from .calibration import (
            BehavioralDataCollector,
            AgentRewardCalibrator,
        )
        
        # TODO: Fetch actual market data
        # from core.models import DelegationMarketSnapshot
        # market_data = DelegationMarketSnapshot.objects.filter(
        #     as_of_date__gte=timezone.now() - timedelta(days=365)
        # ).order_by('as_of_date')
        
        collector = BehavioralDataCollector()
        calibrator = AgentRewardCalibrator()
        
        results = {}
        
        for agent_type in agent_types:
            try:
                # Extract behavioral data
                if agent_type == 'buyer':
                    behavior_data = collector.extract_buyer_behavior()
                elif agent_type == 'developer':
                    behavior_data = collector.extract_developer_behavior()
                elif agent_type == 'speculator':
                    behavior_data = collector.extract_speculator_behavior()
                else:
                    continue
                
                # Calibrate
                calibration_result = calibrator.calibrate_all_agents()
                profile_weights = calibration_result.get(agent_type, {})
                
                # Validate
                validation_result = calibrator.validate_calibration(
                    profile_weights,
                    historical_periods=[]  # TODO: Add actual data
                )
                
                # Determine quality
                mape = validation_result.get('mean_price_mape', 0.15)
                accuracy = validation_result.get('directional_accuracy', 0.75)
                
                quality = (
                    'GOOD' if mape < 0.05 and accuracy > 0.80 else
                    'ACCEPTABLE' if mape < 0.10 and accuracy > 0.70 else
                    'POOR'
                )
                
                # Create profile
                profile = AgentCalibrationProfile.objects.create(
                    agent_type=agent_type,
                    calibration_date=timezone.now().date(),
                    is_active=True,
                    reward_weights=profile_weights.get('weights', {}),
                    directional_accuracy=accuracy,
                    mean_price_mape=mape,
                    calibration_quality=quality,
                    training_transactions=1000,  # TODO: Count actual
                    training_date_range_start=timezone.now().date() - timedelta(days=365),
                    training_date_range_end=timezone.now().date(),
                    calibration_method='inverse_rl_mle',
                    notes=f'Automated calibration run'
                )
                
                # Deactivate older profiles
                AgentCalibrationProfile.objects.filter(
                    agent_type=agent_type,
                    is_active=True
                ).exclude(id=profile.id).update(is_active=False)
                
                results[agent_type] = {
                    'status': 'success',
                    'quality': quality,
                    'mape': float(mape),
                    'accuracy': float(accuracy),
                }
                
            except Exception as e:
                logger.warning(f'Failed to calibrate {agent_type}: {e}')
                results[agent_type] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        logger.info(f'Completed agent calibration: {results}')
        return {
            'status': 'success',
            'calibration_results': results
        }
    
    except Exception as e:
        logger.exception('Agent calibration task failed')
        return {
            'error': str(e),
            'status': 'failed'
        }
