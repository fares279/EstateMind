"""
DeveloperAgent — adds new construction to the market each month.

Construction activity is scaled by the scenario's developer_activity
multiplier.  New builds are marked is_new_build=True and carry a
slight premium over comparable existing units.
"""
from __future__ import annotations

import random
from typing import Optional

from .base import BaseAgent
from ..environment import (
    PROPERTY_TYPES,
    ZONE_KEYS,
    make_property_unit,
    random_zone_key,
)

# New builds per developer per month (base)
BASE_UNITS_PER_MONTH = 2
# Preferred types for developers
DEVELOPER_TYPES = ["apartment", "house"]


class DeveloperAgent(BaseAgent):
    agent_type = "developer"

    def __init__(self, unique_id: int, model, **kwargs):
        super().__init__(unique_id, model, **kwargs)
        self.units_built:  int   = 0
        self.units_sold:   int   = 0
        # Developers focus on 1-3 zones
        num_zones = min(len(ZONE_KEYS), random.randint(1, 3))
        self.focus_zones: list = random.sample(
            [(d, p) for (d, p) in ZONE_KEYS if p in DEVELOPER_TYPES],
            min(num_zones, len([(d, p) for (d, p) in ZONE_KEYS if p in DEVELOPER_TYPES])),
        )

    # ------------------------------------------------------------------
    def step(self, market_state: dict, scenario_params: dict) -> list:
        if not self.is_active:
            return []

        developer_activity = scenario_params.get("developer_activity", 1.0)
        zone_index: dict   = market_state.get("zone_index", {})
        new_listings: list = market_state.get("new_listings_buffer", [])

        actions = []

        # Number of units to release this month
        base = BASE_UNITS_PER_MONTH * developer_activity
        num_units = max(0, int(base * random.uniform(0.5, 1.5)))

        for _ in range(num_units):
            if self.focus_zones:
                delegation, ptype = random.choice(self.focus_zones)
            else:
                delegation, ptype = random_zone_key("apartment")

            # New builds carry a 5-12% premium
            markup = random.uniform(0.05, 0.12)
            prop   = make_property_unit(
                zone_index=zone_index,
                delegation=delegation,
                ptype=ptype,
                is_new_build=True,
                markup_pct=markup,
            )
            prop.seller_id = self.agent_id

            new_listings.append(prop)
            self.units_built += 1
            self.record_action(True)

            actions.append({
                "type":          "new_listing",
                "unit_id":       prop.unit_id,
                "delegation":    delegation,
                "property_type": ptype,
                "ask_per_m2":    prop.ask_price_per_m2,
                "area_m2":       prop.area_m2,
                "is_new_build":  True,
            })

        return actions
