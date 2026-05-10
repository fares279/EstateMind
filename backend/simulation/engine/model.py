"""
TunisiaMarketModel — Mesa 2.x ABM of the Tunisian real-estate market.

Architecture
────────────
  Mesa Model  ←  7 agent types, each a mesa.Agent subclass
  DataCollector  records per-step model metrics
  Staged activation: Government → Developer → Seller → Speculator
                     → Bank → Buyer (shuffled) → Broker

The model is driven by TunisiaRealEstateSimulator (simulator.py) which
calls model.step() once per month and persists results to the Django DB.
"""
from __future__ import annotations

import copy
import logging
import random
from itertools import chain
from typing import List

import mesa
from mesa.time import BaseScheduler
from mesa.datacollection import DataCollector

from .config import get_scenario, get_scale, DELEGATION_DATA, SCENARIOS
from .environment import (
    PropertyUnit,
    ZONE_PRICE_INDEX,
    make_property_unit,
    NATIONAL_ANNUAL_INCOME,
)

logger = logging.getLogger("simulation.model")

PTYPE_WEIGHTS = {"apartment": 55, "house": 30, "land": 10, "commercial": 5}
BUYER_REPLACEMENT_RATE = 0.40


class TunisiaMarketModel(mesa.Model):
    """
    Multi-agent real-estate market model calibrated to Tunisia.
    Inherits from mesa.Model; uses Mesa DataCollector for per-step metrics.
    """

    def __init__(
        self,
        scenario_name: str,
        num_months: int,
        agent_scale: str,
        seed: int = 2026,
        policy_overrides: dict | None = None,
    ) -> None:
        super().__init__()
        random.seed(seed)

        self.scenario_name   = scenario_name
        self.num_months      = num_months
        self.agent_scale     = agent_scale
        self.current_month   = 0

        # Mutable scenario params — GovernmentAgent may modify these mid-run
        self.scenario_params = dict(get_scenario(scenario_name))
        if policy_overrides:
            for k, v in policy_overrides.items():
                if k in self.scenario_params:
                    self.scenario_params[k] = float(v)

        self.scale_cfg = get_scale(agent_scale)

        # Market state shared across agents via this model reference
        self.active_listings:      List[PropertyUnit] = []
        self.all_transactions:     List[dict]         = []
        self.monthly_transactions: List[dict]         = []   # current step only

        # Zone price index — deep copy so mutations don't touch the global
        self.zone_index:      dict  = copy.deepcopy(ZONE_PRICE_INDEX)
        self._prev_avg_price: float = 0.0

        # Mesa scheduler (BaseScheduler = ordered; we bypass it for staged exec)
        self.schedule = BaseScheduler(self)

        # Typed agent lists for staged execution order
        self.buyers_list:      List = []
        self.sellers_list:     List = []
        self.brokers_list:     List = []
        self.developers_list:  List = []
        self.banks_list:       List = []
        self.speculators_list: List = []
        self.governments_list: List = []

        self._init_market()
        self._init_agents()

        # Mesa DataCollector — records one row per model step
        self.datacollector = DataCollector(
            model_reporters={
                "avg_price":       lambda m: round(m._zone_weighted_avg_price(), 2),
                "transactions":    lambda m: len(m.monthly_transactions),
                "active_listings": lambda m: sum(1 for p in m.active_listings if p.is_available),
                "bct_rate":        lambda m: m.scenario_params.get("bct_rate", 0.08),
                "affordability":   lambda m: round(
                    m._zone_weighted_avg_price() / NATIONAL_ANNUAL_INCOME, 2
                ),
                "credit_rate":     lambda m: m.scenario_params.get("credit_approval_rate", 0.55),
            }
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Initialisation helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _init_market(self) -> None:
        sc     = self.scale_cfg
        n_props = sc["buyers"] * 3   # ~3 listings per active buyer

        total_pop   = sum(max(1, d["population"]) for d in DELEGATION_DATA)
        weights     = [max(1, d["population"]) / total_pop for d in DELEGATION_DATA]
        delegations = [d["delegation"] for d in DELEGATION_DATA]

        ptype_keys    = list(PTYPE_WEIGHTS.keys())
        ptype_weights = list(PTYPE_WEIGHTS.values())

        for i in range(n_props):
            deleg = random.choices(delegations, weights=weights, k=1)[0]
            ptype = random.choices(ptype_keys,  weights=ptype_weights, k=1)[0]
            prop  = make_property_unit(
                zone_index=self.zone_index, delegation=deleg, ptype=ptype
            )
            prop.seller_id = f"seller_{i % max(1, sc['sellers']):04d}"
            self.active_listings.append(prop)

    def _init_agents(self) -> None:
        from .agents.buyer      import BuyerAgent
        from .agents.seller     import SellerAgent
        from .agents.broker     import BrokerAgent
        from .agents.developer  import DeveloperAgent
        from .agents.bank       import BankAgent
        from .agents.speculator import SpeculatorAgent
        from .agents.government import GovernmentAgent

        sc  = self.scale_cfg
        uid = 0

        def _add(cls, target_list: list, n: int) -> None:
            nonlocal uid
            for _ in range(n):
                a = cls(uid, self)
                self.schedule.add(a)
                target_list.append(a)
                uid += 1

        # Staged activation order mirrors execution order
        _add(GovernmentAgent, self.governments_list, sc["governments"])
        _add(DeveloperAgent,  self.developers_list,  sc["developers"])
        _add(SellerAgent,     self.sellers_list,     sc["sellers"])
        _add(SpeculatorAgent, self.speculators_list, sc["speculators"])
        _add(BankAgent,       self.banks_list,       sc["banks"])
        _add(BuyerAgent,      self.buyers_list,      sc["buyers"])
        _add(BrokerAgent,     self.brokers_list,     sc["brokers"])

    # ──────────────────────────────────────────────────────────────────────────
    # Main step — one calendar month
    # ──────────────────────────────────────────────────────────────────────────

    def step(self) -> dict:
        """
        Execute one simulation month.
        Returns a snapshot dict that the simulator persists to the DB.
        """
        self.current_month += 1
        self.monthly_transactions = []
        new_listings_buffer: List = []
        mortgage_queue:      List = []

        # Compute per-zone growth vs previous snapshot
        zone_growth: dict = {}
        if self.monthly_transactions is not None and self._prev_avg_price:
            for key, entry in self.zone_index.items():
                prev_p = entry.get("_prev_price", entry["avg_price"])
                zone_growth[key] = (entry["avg_price"] - prev_p) / max(1.0, prev_p)

        affordability = self._zone_weighted_avg_price() / NATIONAL_ANNUAL_INCOME

        market_state = {
            "active_listings":     self.active_listings,
            "buyer_agents":        self.buyers_list,
            "new_listings_buffer": new_listings_buffer,
            "mortgage_queue":      mortgage_queue,
            "zone_index":          self.zone_index,
            "zone_growth":         zone_growth,
            "affordability_index": affordability,
            "current_month":       self.current_month,
        }

        # ── Staged execution ───────────────────────────────────────────────
        for gov in self.governments_list:
            gov.step(market_state, self.scenario_params)

        for dev in self.developers_list:
            dev.step(market_state, self.scenario_params)

        for seller in self.sellers_list:
            seller.step(market_state, self.scenario_params)

        for spec in self.speculators_list:
            spec.step(market_state, self.scenario_params)

        for bank in self.banks_list:
            bank.step(market_state, self.scenario_params)

        # Buyers in random order (Mesa-style shuffle)
        buyers = list(self.buyers_list)
        random.shuffle(buyers)
        for buyer in buyers:
            acts = buyer.step(market_state, self.scenario_params)
            for a in acts:
                if a.get("type") == "purchase":
                    self.monthly_transactions.append(a)
                    self.all_transactions.append(a)

        for broker in self.brokers_list:
            acts = broker.step(market_state, self.scenario_params)
            for a in acts:
                if a.get("type") == "broker_match":
                    txn = {
                        "type":          "purchase",
                        "persona":       "broker_matched",
                        "unit_id":       a.get("unit_id"),
                        "delegation":    a.get("delegation"),
                        "property_type": a.get("property_type"),
                        "price_per_m2":  a.get("price_per_m2", 0),
                        "total_price":   a.get("total_price", 0),
                        "area_m2":       a.get("total_price", 0) / max(1.0, a.get("price_per_m2", 1)),
                    }
                    self.monthly_transactions.append(txn)
                    self.all_transactions.append(txn)

        # Merge new listings from developers / speculators
        self.active_listings.extend(new_listings_buffer)

        # Store previous prices for next step's zone_growth computation
        for entry in self.zone_index.values():
            entry["_prev_price"] = entry["avg_price"]

        # Update zone prices with scenario drift
        self._update_zone_prices()

        # Mesa DataCollector
        self.datacollector.collect(self)

        # Recycle purchased buyers
        self._recycle_buyers()

        # ── Snapshot ──────────────────────────────────────────────────────
        avg_price = self._zone_weighted_avg_price()
        n_avail   = sum(1 for p in self.active_listings if p.is_available)
        n_txns    = len(self.monthly_transactions)
        liquidity = round(min(1.0, n_txns / max(1, n_avail)), 4)

        prev        = self._prev_avg_price or avg_price
        growth_rate = round((avg_price - prev) / max(1.0, prev), 6)
        self._prev_avg_price = avg_price

        return {
            "month":               self.current_month,
            "avg_price":           round(avg_price, 2),
            "transactions":        n_txns,
            "liquidity_score":     liquidity,
            "affordability_index": round(affordability, 2),
            "price_growth_rate":   growth_rate,
            "active_listings":     n_avail,
            "bcb_rate":            self.scenario_params.get("bct_rate", 0.08),
            "credit_rate":         self.scenario_params.get("credit_approval_rate", 0.55),
            "zone_prices":         {
                str(k): round(v["avg_price"], 2)
                for k, v in self.zone_index.items()
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Zone price dynamics
    # ──────────────────────────────────────────────────────────────────────────

    def _update_zone_prices(self) -> None:
        monthly_drift    = self.scenario_params.get("monthly_drift", 0.004)
        price_volatility = self.scenario_params.get("price_volatility", 0.012)
        coastal_penalty  = self.scenario_params.get("coastal_penalty", 0.0)
        demand_mult      = self.scenario_params.get("demand_multiplier", 1.0)

        active_buyers   = sum(1 for b in self.buyers_list if not b.purchased and b.is_active)
        active_listings = max(1, sum(1 for p in self.active_listings if p.is_available))
        demand_pressure = ((active_buyers / active_listings) - 1.0) * 0.004 * demand_mult

        # Seasonal coastal demand (months 5–9 of the simulated year)
        month_in_year = ((self.current_month - 1) % 12) + 1
        is_summer     = 5 <= month_in_year <= 9

        for key, entry in self.zone_index.items():
            is_coastal = entry.get("is_coastal", False)
            noise  = random.gauss(0.0, price_volatility)
            delta  = monthly_drift + demand_pressure + noise

            if is_coastal:
                delta += coastal_penalty
                if is_summer:
                    delta += 0.003   # +0.3% coastal summer boost

            floor = entry.get("min_price", entry["avg_price"] * 0.55)
            entry["avg_price"] = max(floor, entry["avg_price"] * (1.0 + delta))

    # ──────────────────────────────────────────────────────────────────────────
    # Buyer recycling
    # ──────────────────────────────────────────────────────────────────────────

    def _recycle_buyers(self) -> None:
        from .agents.buyer import BuyerAgent

        new_uid = self.schedule.get_agent_count() + 10_000
        for i, b in enumerate(self.buyers_list):
            if b.purchased and random.random() < BUYER_REPLACEMENT_RATE:
                replacement = BuyerAgent(new_uid, self)
                self.schedule.add(replacement)
                self.buyers_list[i] = replacement
                new_uid += 1

    # ──────────────────────────────────────────────────────────────────────────
    # Metric helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _zone_weighted_avg_price(self) -> float:
        """Population-weighted average apartment price per m² × 100 m² reference."""
        total_weight = 0.0
        total_price  = 0.0
        for (d, p), v in self.zone_index.items():
            if p != "apartment":
                continue
            w = float(v.get("population", 1) or 1)
            total_weight += w
            total_price  += v["avg_price"] * w
        if total_weight == 0:
            return 200_000.0
        return round(total_price / total_weight * 100.0, 2)

    # ──────────────────────────────────────────────────────────────────────────
    # Result computation (called by simulator after the run completes)
    # ──────────────────────────────────────────────────────────────────────────

    def agent_outcomes(self) -> list:
        by_type: dict = {}
        all_agents = list(chain(
            self.buyers_list, self.sellers_list, self.brokers_list,
            self.developers_list, self.banks_list, self.speculators_list,
            self.governments_list,
        ))
        for agent in all_agents:
            t = agent.agent_type
            if t not in by_type:
                by_type[t] = {"count": 0, "actions": 0, "successes": 0, "utility": 0.0}
            by_type[t]["count"]     += 1
            by_type[t]["actions"]   += agent.total_actions
            by_type[t]["successes"] += agent.successful_actions
            by_type[t]["utility"]   += agent.utility

        result = []
        for t, s in by_type.items():
            sr = s["successes"] / max(1, s["actions"]) * 100
            result.append({
                "agent_type":    t,
                "count":         s["count"],
                "total_actions": s["actions"],
                "success_rate":  round(sr, 1),
                "avg_utility":   round(s["utility"] / max(1, s["count"]), 2),
            })
        result.sort(key=lambda x: x["agent_type"])
        return result

    def final_metrics(self, monthly_states: list) -> dict:
        if not monthly_states:
            return {}
        prices = [m["avg_price"] for m in monthly_states if m.get("avg_price")]
        first  = prices[0]  if prices else 0.0
        last   = prices[-1] if prices else 0.0
        pct    = (last - first) / max(1.0, first) * 100.0

        n    = len(monthly_states)
        af   = sum(m.get("affordability_index", 0) for m in monthly_states) / max(1, n)
        lq   = sum(m.get("liquidity_score",     0) for m in monthly_states) / max(1, n)
        peak = max((m.get("transactions", 0) for m in monthly_states), default=0)

        return {
            "total_transactions":        len(self.all_transactions),
            "price_change_pct":          round(pct,  2),
            "final_avg_price":           round(last, 2),
            "initial_avg_price":         round(first, 2),
            "peak_monthly_transactions": peak,
            "avg_affordability":         round(af, 2),
            "avg_liquidity":             round(lq, 4),
            "scenario_label":            SCENARIOS.get(self.scenario_name, {}).get("label", self.scenario_name),
        }

    def zone_summary(self) -> list:
        """Per-governorate aggregate price snapshot for the frontend map."""
        gov_data: dict = {}
        for (delegation, ptype), entry in self.zone_index.items():
            gov = entry.get("governorate", "")
            if not gov:
                continue
            if gov not in gov_data:
                gov_data[gov] = {
                    "governorate": gov,
                    "total_price": 0.0,
                    "total_pop":   0.0,
                    "is_coastal":  entry.get("is_coastal", False),
                }
            if ptype == "apartment":
                w = float(entry.get("population", 1) or 1)
                gov_data[gov]["total_price"] += entry["avg_price"] * w
                gov_data[gov]["total_pop"]   += w

        result = []
        for gov, d in gov_data.items():
            avg = d["total_price"] / max(1, d["total_pop"])
            result.append({
                "governorate": gov,
                "avg_price_m2": round(avg, 2),
                "is_coastal":   d["is_coastal"],
            })
        return sorted(result, key=lambda x: x["governorate"])
