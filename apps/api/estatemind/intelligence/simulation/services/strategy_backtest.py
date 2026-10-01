"""Compare simple purchase strategies inside the market simulator.

For every scenario, the agent-based model (engine/model.py) is run n times with
different seeds, and three strategies are scored on each simulated price path:

  * buy_now_hold:      buy in month 1 and hold to the end; return = last / first - 1
  * wait_6_then_buy:   buy in month 7 instead; extra cost = month 7 / month 1 - 1
                       (negative: waiting was cheaper)
  * wait_12_then_buy:  buy at the end of the horizon; extra cost = last / first - 1

The figures are simulated outcomes under the scenario's assumptions, not forecasts,
and they exclude transaction costs, rent and financing. This replaces the RL policy
tester, which sampled returns from fixed distributions instead of running the model.
"""
from __future__ import annotations

from statistics import mean

from ..engine.config import SCENARIOS
from ..engine.model import TunisiaMarketModel

NUM_MONTHS = 12
AGENT_SCALE = 'medium'
CAVEAT = ('Simulated outcomes under the scenario assumptions, starting from price levels calibrated '
          'to listings; not forecasts. Transaction costs, rent and financing are not included.')


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _summary(values: list[float]) -> dict:
    return {'mean_pct': round(100 * mean(values), 2),
            'p05_pct': round(100 * _percentile(values, 0.05), 2),
            'p95_pct': round(100 * _percentile(values, 0.95), 2)}


def price_path(scenario: str, seed: int, num_months: int = NUM_MONTHS, agent_scale: str = AGENT_SCALE) -> list[float]:
    model = TunisiaMarketModel(scenario_name=scenario, num_months=num_months, agent_scale=agent_scale, seed=seed)
    return [model.step()['avg_price'] for _ in range(num_months)]


def backtest(scenarios: list[str] | None = None, n_runs: int = 20, num_months: int = NUM_MONTHS,
             agent_scale: str = AGENT_SCALE) -> dict:
    scenarios = list(scenarios or ['baseline'])
    unknown = [s for s in scenarios if s not in SCENARIOS]
    if unknown:
        raise ValueError(f'Unknown scenario(s): {", ".join(unknown)}')
    if num_months < 7:
        raise ValueError('num_months must be at least 7 (the wait-6 strategy buys in month 7)')

    results = {}
    for scenario in scenarios:
        paths = [price_path(scenario, seed, num_months, agent_scale) for seed in range(n_runs)]
        hold = [p[-1] / p[0] - 1 for p in paths]
        wait6 = [p[6] / p[0] - 1 for p in paths]
        results[scenario] = {
            'runs': n_runs,
            'buy_now_hold': _summary(hold),
            'wait_6_then_buy_extra_cost': _summary(wait6),
            'wait_12_then_buy_extra_cost': _summary(hold),
            'share_of_runs_where_waiting_6_was_cheaper': round(mean(x < 0 for x in wait6), 2),
        }
    return {'status': 'completed', 'kind': 'simulated', 'months': num_months, 'agent_scale': agent_scale,
            'caveat': CAVEAT, 'scenarios': results}
