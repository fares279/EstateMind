"""
GovernmentAgent — macro policy interventions.

Adjusts BCT rate and subsidy levels each month based on observed
affordability.  These mutations feed back into the scenario_params
that all agents read next step.
"""
from __future__ import annotations

import random
from typing import Optional

from .base import BaseAgent

# Affordability thresholds — price / annual_income ratio
AFFORDABILITY_ALARM  = 8.0   # too expensive → ease conditions
AFFORDABILITY_BUBBLE = 4.0   # too cheap / overheating → tighten


class GovernmentAgent(BaseAgent):
    agent_type = "government"

    def __init__(self, unique_id: int, model, **kwargs):
        super().__init__(unique_id, model, **kwargs)
        self.interventions_count: int   = 0
        self.subsidy_budget:      float = 200_000_000.0   # 200M TND total
        self.subsidies_given:     float = 0.0
        self.policy_lag:          int   = 0               # months before next change

    # ------------------------------------------------------------------
    def step(self, market_state: dict, scenario_params: dict) -> list:
        if not self.is_active:
            return []

        if self.policy_lag > 0:
            self.policy_lag -= 1
            return []

        actions         = []
        affordability   = market_state.get("affordability_index", 5.0)
        current_bct     = scenario_params.get("bct_rate", 0.08)
        credit_rate     = scenario_params.get("credit_approval_rate", 0.55)

        # ----------------------------------------------------------------
        # Affordability crisis → ease monetary conditions
        # ----------------------------------------------------------------
        if affordability > AFFORDABILITY_ALARM:
            rate_cut = random.uniform(0.002, 0.008)
            scenario_params["bct_rate"] = max(0.03, current_bct - rate_cut)
            scenario_params["credit_approval_rate"] = min(0.85, credit_rate + 0.05)

            # Issue first-time buyer subsidy
            if self.subsidies_given < self.subsidy_budget:
                subsidy = random.uniform(5_000, 15_000)
                self.subsidies_given += subsidy
                scenario_params["demand_multiplier"] = (
                    scenario_params.get("demand_multiplier", 1.0) * 1.03
                )
                actions.append({
                    "type":       "subsidy_issued",
                    "amount":     round(subsidy, 2),
                    "reason":     "affordability_crisis",
                    "new_bct":    round(scenario_params["bct_rate"], 4),
                })
            else:
                actions.append({
                    "type":    "policy_signal",
                    "signal":  "rate_cut",
                    "new_bct": round(scenario_params["bct_rate"], 4),
                })
            self.interventions_count += 1
            self.record_action(True)
            self.policy_lag = random.randint(2, 4)   # no more changes for 2-4 months

        # ----------------------------------------------------------------
        # Bubble risk → tighten
        # ----------------------------------------------------------------
        elif affordability < AFFORDABILITY_BUBBLE:
            rate_hike = random.uniform(0.002, 0.006)
            scenario_params["bct_rate"] = min(0.18, current_bct + rate_hike)
            scenario_params["credit_approval_rate"] = max(0.15, credit_rate - 0.03)
            scenario_params["speculator_activity"] = (
                scenario_params.get("speculator_activity", 1.0) * 0.90
            )
            self.interventions_count += 1
            self.record_action(True)
            self.policy_lag = random.randint(1, 3)
            actions.append({
                "type":    "policy_signal",
                "signal":  "rate_hike",
                "new_bct": round(scenario_params["bct_rate"], 4),
            })

        return actions
