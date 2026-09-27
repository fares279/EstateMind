"""
Module 10 Requirements 3 & 4: 
- Stochastic Testing Suite (requirement 3)
- Ensemble Simulation Output (requirement 4)

Tests:
1. Reproducibility: Same seed → identical output
2. Variance: Output distribution is meaningful (CV in [0%, 50%])
3. Historical calibration: Baseline scenario matches observed data

Output:
- Ensemble aggregation into quantile bands (P10/P25/P50/P75/P90)
- Probability distributions over outcomes
- Agent outcome summaries
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    """Output from a single simulation run."""
    seed: int
    monthly_prices: List[float]
    monthly_volumes: List[int]
    final_price: float
    total_volume: int
    buyer_transactions: int
    seller_transactions: int
    developer_starts: int
    speculator_exits: int
    median_buyer_return_pct: float
    developer_completions: int
    grounding_error: Optional[str] = None


class StochasticTester:
    """
    Tests that the stochastic simulator has correct properties:
    1. Reproducibility (same seed = same output)
    2. Meaningful variance (CV in target range)
    3. Historical calibration (baseline matches observed)
    """
    
    def __init__(self, simulator_func: Callable):
        """
        Args:
            simulator_func: Function that takes (scenario, n_agents, seed) 
                          and returns SimulationResult
        """
        self.simulator = simulator_func
    
    def test_reproducibility(self, scenario: Dict, 
                             n_agents: str = 'medium',
                             seed: int = 42) -> Dict:
        """
        Test 1: Reproducibility
        
        Runs the same scenario twice with the same seed.
        All outputs must be bit-for-bit identical (or within floating-point epsilon).
        
        If this fails: non-seeded randomness exists in the code
        (common bugs: datetime.now(), os.urandom(), unseeded numpy)
        """
        
        try:
            run_1 = self.simulator(scenario_config=scenario, n_agents=n_agents, seed=seed)
            run_2 = self.simulator(scenario_config=scenario, n_agents=n_agents, seed=seed)
            
            # Handle both dict and SimulationResult formats
            def get_prices(result):
                if isinstance(result, dict):
                    return result.get('monthly_prices', [])
                else:
                    return result.monthly_prices
            
            def get_final_price(result):
                if isinstance(result, dict):
                    return result.get('final_price', 0)
                else:
                    return result.final_price
            
            prices_1 = get_prices(run_1)
            prices_2 = get_prices(run_2)
            final_1 = get_final_price(run_1)
            final_2 = get_final_price(run_2)
            
            # Compare trajectory outputs
            price_close = np.allclose(prices_1, prices_2, rtol=1e-10) if prices_1 and prices_2 else prices_1 == prices_2
            final_price_close = np.isclose(final_1, final_2, rtol=1e-10)
            
            passed = bool(price_close and final_price_close and (final_1 > 0 and final_2 > 0))
            
            return {
                'test': 'reproducibility',
                'seed': seed,
                'passed': passed,
                'price_trajectories_identical': bool(price_close),
                'n_months': len(prices_1) if prices_1 else 0,
                'run_1_final_price': float(final_1) if final_1 else 0,
                'run_2_final_price': float(final_2) if final_2 else 0,
            }
        
        except Exception as e:
            logger.exception('Reproducibility test failed with exception')
            return {
                'test': 'reproducibility',
                'passed': False,
                'error': str(e)
            }
    
    def test_variance(self, scenario: Dict,
                      n_runs: int = 50,
                      n_agents: str = 'medium') -> Dict:
        """
        Test 2: Variance
        
        Runs same scenario with N different seeds.
        Measures variance in final price.
        
        Target:
        - CV > 0: not deterministic (good)
        - CV < 0.50: not chaotic (good)
        - Target range: 5-15% for well-calibrated model
        """
        
        try:
            final_prices = []
            price_trajectories = []
            
            for i in range(n_runs):
                seed = 42 + i
                result = self.simulator(scenario_config=scenario, n_agents=n_agents, seed=seed)
                
                # Handle both dict and SimulationResult formats
                if isinstance(result, dict):
                    final_prices.append(result.get('final_price', 0))
                    price_trajectories.append(result.get('monthly_prices', []))
                else:
                    final_prices.append(result.final_price)
                    price_trajectories.append(result.monthly_prices)
            
            final_prices = np.array(final_prices)
            price_trajectories = [p for p in price_trajectories if p]  # Filter out empty
            
            if not price_trajectories:
                return {
                    'test': 'variance',
                    'passed': False,
                    'error': 'No valid trajectories collected'
                }
            
            trajectories_array = np.array(price_trajectories)
            
            mean_price = np.mean(final_prices)
            std_price = np.std(final_prices)
            cv_price = std_price / mean_price if mean_price > 0 else 0
            
            # Quantile bands
            quantile_bands = {}
            for q in [10, 25, 50, 75, 90]:
                quantile_bands[f'p{q}'] = np.percentile(
                    trajectories_array, q, axis=0
                ).tolist()
            
            assessment = (
                'DETERMINISTIC' if cv_price == 0 else
                'WELL_CALIBRATED' if cv_price < 0.15 else
                'HIGH_VARIANCE' if cv_price < 0.50 else
                'CHAOTIC'
            )
            
            return {
                'test': 'variance',
                'n_runs': n_runs,
                'mean_final_price': float(mean_price),
                'std_final_price': float(std_price),
                'coefficient_of_variation': float(cv_price),
                'passed': bool(0 < cv_price < 0.50),
                'assessment': assessment,
                'quantile_bands': quantile_bands,
                'price_range': {
                    'min': float(np.min(final_prices)),
                    'max': float(np.max(final_prices))
                },
            }
        
        except Exception as e:
            logger.exception('Variance test failed with exception')
            return {
                'test': 'variance',
                'passed': False,
                'error': str(e)
            }
    
    def test_historical_calibration(self, 
                                     n_runs: int = 50,
                                     n_agents: int = 500) -> Dict:
        """
        Test 3: Historical Calibration
        
        Runs baseline scenario (no policy shocks) for past 12 months
        and compares simulated outcomes to actual observed outcomes.
        
        Most important test: if calibrated simulator cannot reproduce
        historical baseline, cannot be trusted for forward scenarios.
        """
        
        try:
            from estatemind.market.core.models import DelegationMarketSnapshot
            
            # Get historical national median prices (last 12 months)
            historical = DelegationMarketSnapshot.objects.filter(
                as_of_date__gte='2025-05-01'
            ).order_by('as_of_date')
            
            if historical.count() < 6:
                return {
                    'test': 'historical_calibration',
                    'status': 'SKIPPED',
                    'reason': 'Insufficient historical data (need 6+ months)',
                    'data_points_available': historical.count()
                }
            
            # Extract actual monthly prices
            actual_monthly_prices = [
                float(s.median_price_per_sqm) 
                for s in historical
            ]
            
            # Run baseline simulation for same period
            baseline_scenario = {
                'scenario_type': 'baseline',
                'interest_rate_shock_pct': 0.0,
                'foreign_investment_multiplier': 1.0,
                'construction_supply_shock_pct': 0.0,
                'diaspora_demand_boost_pct': 0.0,
                'simulation_months': len(actual_monthly_prices),
            }
            
            simulated_trajectories = []
            for seed in range(42, 42 + n_runs):
                result = self.simulator(baseline_scenario, n_agents, seed)
                simulated_trajectories.append(result.monthly_prices)
            
            trajectories_array = np.array(simulated_trajectories)
            simulated_median = np.median(trajectories_array, axis=0)
            simulated_p10 = np.percentile(trajectories_array, 10, axis=0)
            simulated_p90 = np.percentile(trajectories_array, 90, axis=0)
            
            # Check if actual prices within simulated bands
            actual_in_bands = sum(
                1 for i, actual in enumerate(actual_monthly_prices)
                if i < len(simulated_p10) and
                simulated_p10[i] <= actual <= simulated_p90[i]
            )
            
            band_coverage = actual_in_bands / len(actual_monthly_prices)
            
            # MAPE: mean absolute percentage error
            mape = np.mean([
                abs(sim - act) / (act + 1e-10)
                for sim, act in zip(simulated_median, actual_monthly_prices)
            ])
            
            assessment = (
                'WELL_CALIBRATED' if mape < 0.05 else
                'ACCEPTABLE' if mape < 0.10 else
                'MISCALIBRATED'
            )
            
            return {
                'test': 'historical_calibration',
                'n_runs': n_runs,
                'n_months_compared': len(actual_monthly_prices),
                'median_mape': float(mape),
                'actual_in_bands_pct': float(band_coverage),
                'passed': mape < 0.10 and band_coverage >= 0.70,
                'assessment': assessment,
                'simulated_final_price_median': float(simulated_median[-1]),
                'actual_final_price': float(actual_monthly_prices[-1]),
                'final_price_error_pct': float(
                    abs(simulated_median[-1] - actual_monthly_prices[-1]) / 
                    (actual_monthly_prices[-1] + 1e-10)
                )
            }
        
        except Exception as e:
            logger.exception('Historical calibration test failed')
            return {
                'test': 'historical_calibration',
                'status': 'ERROR',
                'error': str(e)
            }
    
    def run_all_tests(self, scenario: Dict,
                      n_agents: int = 200,
                      n_variance_runs: int = 20) -> Dict:
        """Runs all three tests and returns summary."""
        
        results = {
            'reproducibility': self.test_reproducibility(scenario, n_agents),
            'variance': self.test_variance(scenario, n_variance_runs, n_agents),
            'historical_calibration': self.test_historical_calibration(),
            'overall_passed': False,
            'timestamp': datetime.now().isoformat(),
        }
        
        # Overall assessment
        all_passed = all(
            v.get('passed', False)
            for k, v in results.items()
            if k != 'overall_passed' and k != 'timestamp'
        )
        results['overall_passed'] = all_passed
        
        return results


class EnsembleSimulator:
    """
    Runs N simulation instances in parallel and aggregates
    outputs into quantile bands and probability distributions.
    """
    
    DEFAULT_N_RUNS = 50
    QUANTILE_LEVELS = [10, 25, 50, 75, 90]
    
    def __init__(self, simulator_func: Callable = None, max_workers: int = 4):
        """
        Initialize ensemble simulator.
        
        If simulator_func is None, uses the default run_simulation_batch
        from the engine module.
        """
        if simulator_func is None:
            from ..engine import run_simulation_batch
            self.simulator = run_simulation_batch
        else:
            self.simulator = simulator_func
        self.max_workers = max_workers
    
    def run_ensemble(self, 
                     scenario: Dict,
                     n_runs: int = DEFAULT_N_RUNS,
                     n_agents: int = 500) -> Dict:
        """
        Executes ensemble of simulations and returns aggregated output.
        
        Returns quantile bands, probability distributions, and agent outcomes.
        """
        
        results = []
        failed_runs = 0
        
        # Run N simulations with seeds 42 to 42+N
        # Using ThreadPoolExecutor for parallelization
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self.simulator,
                    scenario_config=scenario,
                    n_agents=n_agents,
                    seed=42 + i
                ): i
                for i in range(n_runs)
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.warning(f'Simulation run failed: {e}')
                    failed_runs += 1
        
        # Check if enough runs succeeded
        success_rate = len(results) / n_runs if n_runs > 0 else 0
        if success_rate < 0.80:
            raise RuntimeError(
                f'Ensemble failed: only {len(results)}/{n_runs} runs completed '
                f'({success_rate*100:.0f}%). Target: 80%+. '
                f'Check simulator for crashes.'
            )
        
        logger.info(f'Ensemble complete: {len(results)}/{n_runs} runs, '
                   f'{failed_runs} failures ({(1-success_rate)*100:.1f}%)')
        
        return self._aggregate_results(results)
    
    def _aggregate_results(self, results: List) -> Dict:
        """
        Aggregates N simulation results into quantile bands,
        probability distributions, and summary statistics.
        
        Results can be either SimulationResult objects or dicts
        from run_simulation_batch.
        """
        
        # Filter out failed runs
        successful = [r for r in results if r.get('success', True)]
        if not successful:
            raise RuntimeError(f'All {len(results)} simulation runs failed')
        
        logger.info(f'Aggregating {len(successful)} successful runs')
        
        # Extract price trajectories
        price_trajectories = []
        for r in successful:
            if 'monthly_prices' in r:
                price_trajectories.append(r['monthly_prices'])
            elif isinstance(r, SimulationResult):
                price_trajectories.append(r.monthly_prices)
        
        if not price_trajectories:
            raise RuntimeError('No price trajectories in results')
        
        price_trajectories = np.array(price_trajectories)
        final_prices = np.array([r.get('final_price', 0) for r in successful])
        
        n_months = price_trajectories.shape[1]
        initial_price = price_trajectories[:, 0].mean()
        
        # Compute quantile bands for each month
        monthly_price_bands = {}
        for q in self.QUANTILE_LEVELS:
            monthly_price_bands[f'p{q}'] = (
                np.percentile(price_trajectories, q, axis=0).tolist()
            )
        
        # Growth rates across all runs
        growth_rates = (final_prices - initial_price) / (initial_price + 1e-10) * 100
        
        # Risk metrics
        price_decline_prob = float((growth_rates < 0).mean())
        growth_above_5pct_prob = float((growth_rates > 5).mean())
        growth_above_10pct_prob = float((growth_rates > 10).mean())
        
        return {
            'ensemble_size': len(successful),
            'n_months': n_months,
            'initial_price': float(initial_price),
            
            # Price trajectory bands (main output)
            'monthly_price_bands': monthly_price_bands,
            
            # Summary statistics: final price distribution
            'final_price': {
                'p10': float(np.percentile(final_prices, 10)),
                'p25': float(np.percentile(final_prices, 25)),
                'p50': float(np.percentile(final_prices, 50)),
                'p75': float(np.percentile(final_prices, 75)),
                'p90': float(np.percentile(final_prices, 90)),
                'mean': float(np.mean(final_prices)),
                'std': float(np.std(final_prices)),
                'min': float(np.min(final_prices)),
                'max': float(np.max(final_prices)),
            },
            
            # Growth rate distribution (user-facing)
            'growth_rate_12m': {
                'p10': float(np.percentile(growth_rates, 10)),
                'p25': float(np.percentile(growth_rates, 25)),
                'p50': float(np.percentile(growth_rates, 50)),
                'p75': float(np.percentile(growth_rates, 75)),
                'p90': float(np.percentile(growth_rates, 90)),
                'pessimistic_label': f'{np.percentile(growth_rates, 10):.1f}%',
                'median_label': f'{np.percentile(growth_rates, 50):.1f}%',
                'optimistic_label': f'{np.percentile(growth_rates, 90):.1f}%',
            },
            
            # Probability distribution
            'probabilities': {
                'price_decline': price_decline_prob,
                'growth_above_5pct': growth_above_5pct_prob,
                'growth_above_10pct': growth_above_10pct_prob,
            },
            
            'generated_at': datetime.now().isoformat(),
        }


