"""
BrokerAgent — matches unmatched buyers with suitable listings.

Takes a 3% commission on matched transactions.
Each broker processes a random subset of the available listings per step.
"""
from __future__ import annotations

import random
from typing import Optional

from .base import BaseAgent
from ..environment import PropertyUnit


COMMISSION_RATE = 0.03   # 3% of transaction value


class BrokerAgent(BaseAgent):
    agent_type = "broker"

    def __init__(self, unique_id: int, model, **kwargs):
        super().__init__(unique_id, model, **kwargs)
        self.commission_earned: float = 0.0
        self.match_attempts:    int   = 0
        self.matches_made:      int   = 0

    # ------------------------------------------------------------------
    def step(self, market_state: dict, scenario_params: dict) -> list:
        if not self.is_active:
            return []

        actions = []
        listings: list  = market_state.get("active_listings", [])
        buyers: list    = market_state.get("buyer_agents", [])

        # Active unsold listings
        available = [p for p in listings if p.is_available]
        if not available:
            return []

        # Buyers who haven't purchased yet
        seeking = [b for b in buyers if not b.purchased and b.is_active]
        if not seeking:
            return []

        # Broker operates on a limited pipeline per month
        pipeline_size = max(3, int(len(available) * random.uniform(0.05, 0.15)))
        pipeline = random.sample(available, min(pipeline_size, len(available)))

        for prop in pipeline:
            if not prop.is_available:
                continue
            # Find a matching buyer
            matches = [
                b for b in seeking
                if not b.purchased
                and prop.property_type in b.preferred_types
                and prop.total_ask_price <= b.budget * 1.05
            ]
            if not matches:
                self.match_attempts += 1
                continue

            buyer = random.choice(matches)
            self.match_attempts += 1

            # Execute match at ask price (broker negotiated)
            offer_per_m2 = prop.ask_price_per_m2 * random.uniform(0.97, 1.00)
            accepted = offer_per_m2 >= prop.reservation_price_per_m2

            if accepted:
                prop.is_available      = False
                prop.sold_price_per_m2 = round(offer_per_m2, 2)
                prop.buyer_id          = buyer.agent_id
                buyer.purchased        = True

                commission = offer_per_m2 * prop.area_m2 * COMMISSION_RATE
                self.commission_earned += commission
                self.matches_made      += 1
                self.record_action(True, utility_delta=commission)

                actions.append({
                    "type":          "broker_match",
                    "unit_id":       prop.unit_id,
                    "buyer_id":      buyer.agent_id,
                    "delegation":    prop.delegation,
                    "property_type": prop.property_type,
                    "price_per_m2":  round(offer_per_m2, 2),
                    "total_price":   round(offer_per_m2 * prop.area_m2, 2),
                    "commission":    round(commission, 2),
                })
            else:
                self.record_action(False)

        return actions
