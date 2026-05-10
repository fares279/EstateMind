"""
SellerAgent — lists properties and negotiates with buyers.

Behaviour:
- Each seller owns 1-3 properties placed on the market at start.
- Ask price is reduced 2-3% per month after 3 months on market.
- Accepts any offer >= reservation_price.
"""
from __future__ import annotations

import random
from typing import List, Optional

from .base import BaseAgent
from ..environment import (
    PropertyUnit,
    ZONE_PRICE_INDEX,
    ZONE_KEYS,
    make_property_unit,
    random_zone_key,
)


class SellerAgent(BaseAgent):
    agent_type = "seller"

    def __init__(self, unique_id: int, model, **kwargs):
        super().__init__(unique_id, model, **kwargs)
        self.num_properties:  int   = random.randint(1, 3)
        self.sold_count:      int   = 0
        self.aspiration_level: float = random.uniform(1.02, 1.12)  # ask above market
        self.price_reduction_rate: float = random.uniform(0.02, 0.03)  # per month after patience
        self.patience_months: int   = random.randint(2, 4)
        # Properties are created in simulator.initialise_market()
        self.property_ids:    list  = []

    # ------------------------------------------------------------------
    def step(self, market_state: dict, scenario_params: dict) -> list:
        if not self.is_active:
            return []

        actions = []
        listings: list = market_state.get("active_listings", [])

        # Find own unsold listings
        own = [p for p in listings if p.seller_id == self.agent_id and p.is_available]

        for prop in own:
            prop.months_on_market += 1
            # Apply ask reduction after patience period
            if prop.months_on_market > self.patience_months:
                reduction = self.price_reduction_rate * random.uniform(0.8, 1.2)
                new_ask = prop.ask_price_per_m2 * (1.0 - reduction)
                # Never drop below reservation price
                new_ask = max(prop.reservation_price_per_m2, new_ask)
                if new_ask < prop.ask_price_per_m2:
                    prop.ask_price_per_m2 = round(new_ask, 2)
                    self.record_action(True)
                    actions.append({
                        "type":       "price_reduction",
                        "unit_id":    prop.unit_id,
                        "new_ask":    prop.ask_price_per_m2,
                        "months_on":  prop.months_on_market,
                    })

        # Count how many have sold this step
        sold_this_step = [
            p for p in market_state.get("active_listings", [])
            if p.seller_id == self.agent_id and not p.is_available and p.sold_price_per_m2
        ]
        for prop in sold_this_step:
            revenue = prop.sold_price_per_m2 * prop.area_m2 if prop.sold_price_per_m2 else 0
            self.record_action(True, utility_delta=revenue * 0.01)

        return actions
