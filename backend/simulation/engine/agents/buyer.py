"""
BuyerAgent — searches the market and submits purchase offers.

Personas  (approximate national distribution):
    first_time  35%  — price-sensitive, needs mortgage, prefers apartments
    upgrader    20%  — moves up from current home, moderate budget
    investor    15%  — yield-seeking, prefers apartments / commercial
    diaspora    15%  — remittance-funded, targets coastal/premium areas
    speculator  15%  — short-hold, targets high-appreciation zones
"""
from __future__ import annotations

import random
from typing import Optional

from .base import BaseAgent
from ..environment import PropertyUnit, NATIONAL_ANNUAL_INCOME

# Persona weights used when creating a pool of buyers
PERSONA_WEIGHTS = {
    "first_time": 0.35,
    "upgrader":   0.20,
    "investor":   0.15,
    "diaspora":   0.15,
    "speculator": 0.15,
}

# Budget multipliers relative to NATIONAL_ANNUAL_INCOME * 10 (≈ 10-year salary)
BUDGET_MULTIPLIERS = {
    "first_time": (0.6,  1.0),
    "upgrader":   (1.0,  2.0),
    "investor":   (1.0,  3.0),
    "diaspora":   (1.5,  4.0),
    "speculator": (0.8,  2.5),
}

# Preferred property types by persona
PREFERRED_TYPES = {
    "first_time": ["apartment"],
    "upgrader":   ["apartment", "house"],
    "investor":   ["apartment", "commercial"],
    "diaspora":   ["apartment", "house"],
    "speculator": ["apartment", "house"],
}

# Urgency weights — how aggressively the buyer bids
URGENCY = {
    "first_time": 0.50,
    "upgrader":   0.65,
    "investor":   0.60,
    "diaspora":   0.80,
    "speculator": 0.90,
}


def random_persona() -> str:
    keys   = list(PERSONA_WEIGHTS.keys())
    weights = [PERSONA_WEIGHTS[k] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


class BuyerAgent(BaseAgent):
    agent_type = "buyer"

    def __init__(self, unique_id: int, model, persona: Optional[str] = None, **kwargs):
        super().__init__(unique_id, model, **kwargs)
        self.persona:          str   = persona or random_persona()
        lo, hi                       = BUDGET_MULTIPLIERS[self.persona]
        self.budget:           float = NATIONAL_ANNUAL_INCOME * 10 * random.uniform(lo, hi)
        self.preferred_types:  list  = PREFERRED_TYPES[self.persona]
        self.urgency:          float = URGENCY[self.persona] * random.uniform(0.8, 1.2)
        self.urgency           = min(1.0, self.urgency)
        self.has_mortgage:     bool  = self.persona in ("first_time", "upgrader")
        self.mortgage_approved: bool = False
        self.target_delegation: Optional[str] = None
        self.purchased:        bool  = False  # leaves market once purchased

    # ------------------------------------------------------------------
    def step(self, market_state: dict, scenario_params: dict) -> list:
        if self.purchased or not self.is_active:
            return []

        actions = []
        dm = scenario_params.get("demand_multiplier", 1.0)
        credit_rate = scenario_params.get("credit_approval_rate", 0.55)

        # --- Mortgage pre-approval (if not yet done) ---
        if self.has_mortgage and not self.mortgage_approved:
            # Simple probability gate — bank agent does fine-grained LTV/DTI
            approval_prob = credit_rate * dm * random.uniform(0.8, 1.2)
            self.mortgage_approved = random.random() < approval_prob
            actions.append({
                "type":    "mortgage_application",
                "persona": self.persona,
                "approved": self.mortgage_approved,
            })
            if not self.mortgage_approved:
                self.record_action(False)
                return actions  # cannot buy this month

        # --- Search for matching listings ---
        listings: list = market_state.get("active_listings", [])
        candidates = [
            p for p in listings
            if p.is_available
            and p.property_type in self.preferred_types
            and p.total_ask_price <= self.budget * random.uniform(0.95, 1.10)
        ]

        if not candidates:
            self.record_action(False)
            return actions

        # Pick the best (cheapest per m²) among a random sample
        sample_size = min(len(candidates), max(1, int(len(candidates) * 0.25)))
        sample = random.sample(candidates, sample_size)
        chosen: PropertyUnit = min(sample, key=lambda p: p.ask_price_per_m2)

        # --- Submit offer ---
        # Offer is a fraction of ask, driven by urgency
        offer_ratio = random.uniform(0.88, 0.99) + self.urgency * 0.05
        offer_per_m2 = chosen.ask_price_per_m2 * min(offer_ratio, 1.05)

        # Accept if offer >= reservation price
        accepted = offer_per_m2 >= chosen.reservation_price_per_m2

        if accepted:
            chosen.is_available      = False
            chosen.sold_price_per_m2 = round(offer_per_m2, 2)
            chosen.buyer_id          = self.agent_id
            self.purchased           = True
            gain = (chosen.budget_headroom if hasattr(chosen, "budget_headroom") else 0)
            self.record_action(True, utility_delta=self.budget * 0.02)
            actions.append({
                "type":           "purchase",
                "persona":        self.persona,
                "unit_id":        chosen.unit_id,
                "delegation":     chosen.delegation,
                "property_type":  chosen.property_type,
                "price_per_m2":   round(offer_per_m2, 2),
                "total_price":    round(offer_per_m2 * chosen.area_m2, 2),
                "area_m2":        chosen.area_m2,
            })
        else:
            self.record_action(False)
            actions.append({
                "type":    "offer_rejected",
                "persona": self.persona,
                "unit_id": chosen.unit_id,
            })

        return actions
