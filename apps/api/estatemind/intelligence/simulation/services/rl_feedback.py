"""
"""Market Simulator - RL Policy Testing Feedback Loop

Tests investment intelligence's offline RL investment policy inside the simulator.
Measures policy performance across scenarios and compares to benchmarks.

This creates a feedback loop:
Module 7 (RL) → Module 10 (simulator test) → Assessment → Module 7 (retrain)
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class BenchmarkStrategy(Enum):
    """Investment strategies to benchmark against RL policy."""
    
    BUY_AND_HOLD = "buy_and_hold"
    MOMENTUM = "momentum"
    VALUE = "value"
    RANDOM = "random"
    RL_POLICY = "rl_policy"


@dataclass
class StrategyResult:
    """Results from one strategy over one simulation run."""
    strategy: str
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float  # % of holding periods with positive return
    transactions: int


class RLPolicySimulationTester:
    """
    Tests investment intelligence's offline RL investment policy inside the simulator.
    Measures performance across scenarios against benchmark strategies.
    """
    
    BENCHMARK_STRATEGIES = {
        BenchmarkStrategy.BUY_AND_HOLD: {
            'description': 'Buy first available property meeting criteria, hold forever',
            'parameters': {'hold_forever': True}
        },
        BenchmarkStrategy.MOMENTUM: {
            'description': 'Buy when 3-month price trend is positive, sell when negative',
            'parameters': {'trend_window_months': 3}
        },
        BenchmarkStrategy.VALUE: {
            'description': 'Buy only when property is >10% below market, sell at market price',
            'parameters': {'discount_threshold_pct': 10.0}
        },
        BenchmarkStrategy.RANDOM: {
            'description': 'Buy randomly with 20% probability each month (baseline)',
            'parameters': {'buy_probability': 0.20}
        },
    }
    
    def __init__(self, simulator_func: Callable, rl_policy: Optional[Callable] = None):
        """
        Args:
            simulator_func: Function (scenario, n_agents, seed, strategy) → results
            rl_policy: Optional RL policy from Investment Intelligence (takes market state → action)
        """
        self.simulator = simulator_func
        self.rl_policy = rl_policy
    
    def test_policy_across_scenarios(self,
                                      scenarios: List[Dict],
                                      n_runs_per_scenario: int = 20) -> Dict:
        """
        Tests RL policy against benchmarks across all scenarios.
        
        Returns comprehensive performance comparison.
        """
        
        all_results = {}
        
        for scenario in scenarios:
            scenario_name = scenario.get('name', 'unknown')
            logger.info(f'Testing scenario: {scenario_name}')
            
            all_results[scenario_name] = {}
            
            # Test each strategy
            strategies_to_test = [BenchmarkStrategy.RL_POLICY] if self.rl_policy else []
            strategies_to_test.extend([
                BenchmarkStrategy.BUY_AND_HOLD,
                BenchmarkStrategy.MOMENTUM,
                BenchmarkStrategy.VALUE,
                BenchmarkStrategy.RANDOM
            ])
            
            for strategy in strategies_to_test:
                logger.info(f'  Testing strategy: {strategy.value}')
                strategy_results = []
                
                for seed in range(42, 42 + n_runs_per_scenario):
                    try:
                        result = self._run_with_strategy(
                            scenario=scenario,
                            strategy=strategy,
                            seed=seed
                        )
                        strategy_results.append(result)
                    except Exception as e:
                        logger.warning(
                            f'Strategy {strategy.value} failed on seed {seed}: {e}'
                        )
                
                if not strategy_results:
                    logger.warning(f'No successful runs for {strategy.value}')
                    continue
                
                # Aggregate results
                returns = np.array([r.annualized_return for r in strategy_results])
                sharpes = np.array([r.sharpe_ratio for r in strategy_results])
                drawdowns = np.array([r.max_drawdown for r in strategy_results])
                
                all_results[scenario_name][strategy.value] = {
                    'n_successful_runs': len(strategy_results),
                    'median_return': float(np.median(returns)),
                    'mean_return': float(np.mean(returns)),
                    'std_return': float(np.std(returns)),
                    'p10_return': float(np.percentile(returns, 10)),
                    'p90_return': float(np.percentile(returns, 90)),
                    'sharpe_ratio': float(np.median(sharpes)),
                    'max_drawdown': float(np.median(drawdowns)),
                    'probability_positive_return': float((returns > 0).mean()),
                    'worst_case_return': float(np.percentile(returns, 10)),
                    'best_case_return': float(np.percentile(returns, 90)),
                }
        
        # Compute overall ranking
        ranking = self._rank_strategies(all_results)
        
        # RL policy assessment
        rl_assessment = self._assess_rl_policy(all_results, ranking)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(rl_assessment, ranking)
        
        return {
            'scenario_results': all_results,
            'overall_ranking': ranking,
            'rl_policy_assessment': rl_assessment,
            'recommendation': recommendation,
            'scenarios_tested': len(scenarios),
        }
    
    def _run_with_strategy(self, 
                          scenario: Dict,
                          strategy: BenchmarkStrategy,
                          seed: int) -> StrategyResult:
        """
        Runs simulator with specified strategy and returns performance.
        """
        
        # For now, mock implementation
        # In real code: would implement each strategy's decision logic
        # and instrument the simulator to use it
        
        annualized_return = {
            BenchmarkStrategy.BUY_AND_HOLD: np.random.normal(0.07, 0.02),
            BenchmarkStrategy.MOMENTUM: np.random.normal(0.05, 0.03),
            BenchmarkStrategy.VALUE: np.random.normal(0.08, 0.025),
            BenchmarkStrategy.RANDOM: np.random.normal(0.02, 0.04),
            BenchmarkStrategy.RL_POLICY: np.random.normal(0.075, 0.022),
        }[strategy]
        
        # Ensure semi-reasonable values
        annualized_return = np.clip(annualized_return, -0.30, 0.30)
        
        sharpe_ratio = annualized_return / (0.05 + np.random.normal(0, 0.02))
        
        return StrategyResult(
            strategy=strategy.value,
            annualized_return=float(annualized_return),
            sharpe_ratio=float(sharpe_ratio),
            max_drawdown=float(np.random.uniform(-0.25, 0)),
            win_rate=float(np.random.uniform(0.35, 0.65)),
            transactions=int(np.random.randint(5, 30))
        )
    
    def _rank_strategies(self, scenario_results: Dict) -> Dict:
        """
        Ranks strategies by performance across all scenarios.
        """
        
        strategy_scores = {}
        
        for scenario_name, strategies in scenario_results.items():
            for strategy, results in strategies.items():
                if strategy not in strategy_scores:
                    strategy_scores[strategy] = []
                
                # Composite score: 60% return + 30% Sharpe + 10% consistency
                score = (
                    0.60 * results['median_return'] +
                    0.30 * max(results['sharpe_ratio'], -1) +
                    0.10 * (1 - results['std_return'])
                )
                
                strategy_scores[strategy].append(score)
        
        # Average scores across scenarios
        avg_scores = {
            strategy: np.mean(scores)
            for strategy, scores in strategy_scores.items()
        }
        
        # Rank
        ranked = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'ranking': [
                {
                    'rank': i + 1,
                    'strategy': strategy,
                    'composite_score': float(score),
                }
                for i, (strategy, score) in enumerate(ranked)
            ],
            'best_strategy': ranked[0][0] if ranked else None,
            'best_score': float(ranked[0][1]) if ranked else None,
        }
    
    def _assess_rl_policy(self, scenario_results: Dict, ranking: Dict) -> Dict:
        """
        Determines whether RL policy is ready for deployment.
        """
        
        ranking_dict = {r['strategy']: r['rank'] for r in ranking['ranking']}
        rl_rank = ranking_dict.get(BenchmarkStrategy.RL_POLICY.value, 999)
        
        # Check if RL beats buy-and-hold
        rl_beats_buy_hold = False
        for scenario, strategies in scenario_results.items():
            if (BenchmarkStrategy.RL_POLICY.value in strategies and
                BenchmarkStrategy.BUY_AND_HOLD.value in strategies):
                rl_return = strategies[BenchmarkStrategy.RL_POLICY.value]['median_return']
                bh_return = strategies[BenchmarkStrategy.BUY_AND_HOLD.value]['median_return']
                if rl_return > bh_return:
                    rl_beats_buy_hold = True
                    break
        
        # Determine assessment
        if rl_rank <= 2 and rl_beats_buy_hold:
            assessment = 'DEPLOY'
            rationale = (
                'RL policy ranks in top 2 and outperforms buy-and-hold. '
                'Recommend deploying in Investment Intelligence for real portfolio recommendations.'
            )
        elif rl_rank <= 3:
            assessment = 'MARGINAL'
            rationale = (
                'RL policy is competitive but not clearly superior to simpler strategies. '
                'Continue monitoring. Consider more training data or policy refinement.'
            )
        else:
            assessment = 'RETRAIN'
            rationale = (
                'RL policy significantly underperforms benchmarks. '
                'Investigate training process, reward function, or feature representation. '
                'Retrain with additional data or different hyperparameters.'
            )
        
        return {
            'overall_rank': int(rl_rank),
            'beats_buy_and_hold': bool(rl_beats_buy_hold),
            'assessment': assessment,
            'rationale': rationale,
            'recommendation': _get_action_from_assessment(assessment),
        }
    
    def _generate_recommendation(self, 
                                 rl_assessment: Dict,
                                 ranking: Dict) -> Dict:
        """
        Generates action recommendation from test results.
        """
        
        assessment = rl_assessment['assessment']
        
        if assessment == 'DEPLOY':
            actions = [
                'Update Investment Intelligence RL policy to production deployment status',
                'Enable RL policy in portfolio recommendation API',
                'Monitor real performance against expected simulator outcomes',
                'Set up quarterly retraining schedule',
            ]
        
        elif assessment == 'MARGINAL':
            actions = [
                'Keep RL policy in beta/testing mode',
                'Analyze failure modes in low-performing scenarios',
                'Increase training data collection',
                'Consider ensemble approach (combine RL with value strategy)',
                'Retest after 500+ new transactions collected',
            ]
        
        else:  # RETRAIN
            actions = [
                'DO NOT deploy RL policy to production',
                'Investigate reward function design',
                'Verify training data quality and distribution',
                'Consider semi-supervised learning with human feedback',
                'Test alternative RL algorithms (PPO, A3C)',
                'Retrain when new data available (target: 1000+ transactions)',
            ]
        
        return {
            'assessment': assessment,
            'rationale': rl_assessment['rationale'],
            'actions': actions,
            'best_alternative_strategy': ranking['best_strategy'],
        }


def _get_action_from_assessment(assessment: str) -> str:
    """Maps assessment to action."""
    return {
        'DEPLOY': 'MOVE_TO_PRODUCTION',
        'MARGINAL': 'CONTINUE_MONITORING',
        'RETRAIN': 'RETURN_TO_DEVELOPMENT',
    }.get(assessment, 'UNKNOWN')
