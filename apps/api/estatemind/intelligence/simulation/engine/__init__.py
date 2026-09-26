"""
Module 10 Integration: Simulation Engine Wrapper

Provides a clean interface for the ensemble system to run multiple
simulations in parallel without database overhead.
"""

def run_simulation_batch(scenario_config: dict,
                         n_agents: str = 'medium',
                         seed: int = 42,
                         num_months: int = 12) -> dict:
    """
    Execute a single simulation run and return results.
    
    This is the integration point between the simulator's ensemble framework
    and the existing TunisiaMarketModel engine.
    
    Args:
        scenario_config: Dict with keys like 'interest_rate_shock_pct',
                        'construction_supply_shock_pct', etc.
                        Maps to SCENARIOS in config.py
        n_agents: Agent scale ('small', 'medium', 'large') — maps to
                 agent_scale parameter
        seed: Random seed for reproducibility
        num_months: Duration in months (default 12)
    
    Returns:
        Dict with:
        - monthly_states: List of dicts (one per month)
        - final_metrics: Dict with aggregate metrics
        - final_price: Last month's median price
        - growth_rate_12m: Annual growth rate
        - success: Boolean (True if completed without error)
        - error: Error message if failed
    """
    import logging
    logger = logging.getLogger('estatemind.intelligence.simulation.engine')
    
    try:
        from .model import TunisiaMarketModel
        
        # Map scenario_config dict to scenario_name
        # Simplest mapping: use 'baseline' as default unless specific markers present
        scenario_name = 'baseline'
        policy_overrides = {}
        
        if scenario_config:
            # Extract any parameter overrides from config
            for key, value in scenario_config.items():
                if key in ['interest_rate_shock_pct', 'foreign_investment_multiplier',
                           'construction_supply_shock_pct', 'diaspora_demand_boost_pct',
                           'bct_rate', 'credit_approval_rate']:
                    policy_overrides[key] = float(value)
        
        # Create and run the model
        model = TunisiaMarketModel(
            scenario_name=scenario_name,
            num_months=num_months,
            agent_scale=n_agents,
            seed=seed,
            policy_overrides=policy_overrides,
        )
        
        monthly_states = []
        for month in range(num_months):
            state = model.step()
            monthly_states.append(state)
        
        # Extract final results
        final_metrics = model.final_metrics(monthly_states)
        
        # Compute price trajectory and growth
        prices = [s.get('avg_price', 0) for s in monthly_states]
        final_price = prices[-1] if prices else 0
        initial_price = prices[0] if prices else final_price
        growth_rate_12m = (final_price - initial_price) / max(1.0, initial_price) if initial_price else 0
        
        return {
            'success': True,
            'monthly_states': monthly_states,
            'final_metrics': final_metrics,
            'monthly_prices': prices,
            'final_price': final_price,
            'growth_rate_12m': growth_rate_12m,
            'seed': seed,
            'months': num_months,
        }
    
    except Exception as e:
        logger.exception(f'Simulation run failed (seed={seed})')
        return {
            'success': False,
            'error': str(e),
            'seed': seed,
            'monthly_states': [],
            'monthly_prices': [],
        }
