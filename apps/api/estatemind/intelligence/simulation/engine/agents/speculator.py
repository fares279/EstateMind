"""
SpeculatorAgent — buys in trending zones and flips after hold_horizon months.

Strategy:
- Scan market for zones with high price_growth_rate.
- Buy below ask if possible, hold for hold_horizon months.
- Re-list at ask * flip_threshold if market still hot.
- Cut losses and list at -5% if market has cooled.
"""
from __future__ import annotations

import random
from typing import Optional

from .base import BaseAgent
from ..environment import PropertyUnit, make_property_unit, ZONE_KEYS


class SpeculatorAgent(BaseAgent):
    agent_type = "speculator"

    def __init__(self, unique_id: int, model, **kwargs):
        super().__init__(unique_id, model, **kwargs)
        self.hold_horizon:    int   = random.randint(3, 9)   # months
        self.flip_threshold:  float = 1.0 + random.uniform(0.05, 0.20)
        self.capital:         float = random.uniform(50_000, 500_000)
        self.portfolio:       list  = []   # list of (PropertyUnit, purchase_price, months_held)
        self.realized_profit: float = 0.0
        self.max_portfolio:   int   = random.randint(2, 5)

    # ------------------------------------------------------------------
    def step(self, market_state: dict, scenario_params: dict) -> list:
        if not self.is_active:
            return []

        speculator_activity = scenario_params.get("speculator_activity", 1.0)
        investor_multiplier = scenario_params.get("investor_multiplier", 1.0)
        active_factor       = speculator_activity * investor_multiplier

        # If market conditions are hostile, sit out
        if random.random() > min(0.95, 0.40 * active_factor):
            return []

        actions = []
        listings: list   = market_state.get("active_listings", [])
        new_listings: list = market_state.get("new_listings_buffer", [])
        zone_growth: dict  = market_state.get("zone_growth", {})

        # ----------------------------------------------------------------
        # 1. Age & sell existing portfolio items
        # ----------------------------------------------------------------
        still_holding = []
        for (prop, purchase_ppem2, months_held) in self.portfolio:
            months_held += 1
            current_zone_growth = zone_growth.get((prop.delegation, prop.property_type), 0.0)

            should_sell = (
                months_held >= self.hold_horizon
                or current_zone_growth < -0.005   # market cooling
            )

            if should_sell:
                if current_zone_growth >= 0:
                    sell_ppem2 = purchase_ppem2 * (self.flip_threshold + current_zone_growth * 2)
                else:
                    sell_ppem2 = purchase_ppem2 * 0.95   # cut losses

                profit = (sell_ppem2 - purchase_ppem2) * prop.area_m2
                self.realized_profit += profit
                self.capital         += sell_ppem2 * prop.area_m2
                self.record_action(profit > 0, utility_delta=profit)

                # Put back on market as a re-listing
                prop.ask_price_per_m2 = round(sell_ppem2, 2)
                prop.reservation_price_per_m2 = round(purchase_ppem2 * 1.01, 2)
                prop.is_available     = True
                prop.seller_id        = self.agent_id
                prop.months_on_market = 0
                new_listings.append(prop)

                actions.append({
                    "type":          "flip_list",
                    "unit_id":       prop.unit_id,
                    "delegation":    prop.delegation,
                    "property_type": prop.property_type,
                    "purchase_ppem2": round(purchase_ppem2, 2),
                    "ask_ppem2":     round(sell_ppem2, 2),
                    "profit_est":    round(profit, 2),
                    "months_held":   months_held,
                })
            else:
                still_holding.append((prop, purchase_ppem2, months_held))

        self.portfolio = still_holding

        # ----------------------------------------------------------------
        # 2. Buy new properties if capital allows and portfolio not full
        # ----------------------------------------------------------------
        if len(self.portfolio) >= self.max_portfolio:
            return actions

        # Find hot zones (positive growth)
        hot_zones = [k for k, g in zone_growth.items() if g > 0.003]
        if not hot_zones and ZONE_KEYS:
            hot_zones = [random.choice(ZONE_KEYS)]

        # Available listings in hot zones
        candidates = [
            p for p in listings
            if p.is_available
            and (p.delegation, p.property_type) in hot_zones
            and p.total_ask_price <= self.capital * 0.7
        ]

        if not candidates:
            return actions

        # Buy the cheapest per m²
        candidates.sort(key=lambda p: p.ask_price_per_m2)
        target = candidates[0]

        buy_price = target.ask_price_per_m2 * random.uniform(0.93, 1.00)
        if buy_price < target.reservation_price_per_m2:
            return actions   # seller won't accept

        cost = buy_price * target.area_m2
        if cost > self.capital:
            return actions

        target.is_available      = False
        target.sold_price_per_m2 = round(buy_price, 2)
        target.buyer_id          = self.agent_id
        self.capital            -= cost
        self.portfolio.append((target, buy_price, 0))
        self.record_action(True)

        actions.append({
            "type":          "speculative_buy",
            "unit_id":       target.unit_id,
            "delegation":    target.delegation,
            "property_type": target.property_type,
            "price_per_m2":  round(buy_price, 2),
            "total_cost":    round(cost, 2),
            "portfolio_size": len(self.portfolio),
        })

        return actions
