"""
BaseAgent — Mesa 2.x base class for all simulation agents.

All EstateMind agents inherit from this.  It wraps mesa.Agent and adds
the utility-tracking helpers used throughout the step logic.
"""
from __future__ import annotations

import random
from typing import Any

import mesa


class BaseAgent(mesa.Agent):
    """
    Thin Mesa 2.x wrapper that adds:
        - is_active  flag
        - total_actions / successful_actions counters
        - utility  (cumulative profit / satisfaction)
        - record_action() helper
        - agent_id  alias = str(unique_id)   (backward-compat)
    """

    agent_type: str = "base"

    def __init__(self, unique_id: int, model: mesa.Model, **kwargs: Any) -> None:
        super().__init__(unique_id, model)
        self.agent_id:             str   = str(unique_id)
        self.is_active:            bool  = True
        self.total_actions:        int   = 0
        self.successful_actions:   int   = 0
        self.utility:              float = 0.0

        for k, v in kwargs.items():
            setattr(self, k, v)

    # ------------------------------------------------------------------
    # Core interface (override in subclasses)
    # ------------------------------------------------------------------
    def step(self, market_state: dict, scenario_params: dict) -> list:  # type: ignore[override]
        return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @property
    def success_rate(self) -> float:
        if self.total_actions == 0:
            return 0.0
        return self.successful_actions / self.total_actions

    def record_action(self, success: bool, utility_delta: float = 0.0) -> None:
        self.total_actions += 1
        if success:
            self.successful_actions += 1
        self.utility += utility_delta

    def to_dict(self) -> dict:
        return {
            "agent_id":           self.agent_id,
            "agent_type":         self.agent_type,
            "is_active":          self.is_active,
            "total_actions":      self.total_actions,
            "successful_actions": self.successful_actions,
            "success_rate":       round(self.success_rate, 4),
            "utility":            round(self.utility, 2),
        }

    # ------------------------------------------------------------------
    # Randomness helpers (delegates to stdlib random for reproducibility)
    # ------------------------------------------------------------------
    @staticmethod
    def rand() -> float:
        return random.random()

    @staticmethod
    def randrange(lo: float, hi: float) -> float:
        return random.uniform(lo, hi)

    @staticmethod
    def gauss(mu: float = 0.0, sigma: float = 1.0) -> float:
        return random.gauss(mu, sigma)
