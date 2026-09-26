"""
BankAgent — evaluates mortgage applications with LTV and DTI checks.

Each month the bank reviews pending loan applications in the market
state queue and approves/rejects based on scenario credit conditions.

LTV (Loan-to-Value) <= 80%  by default (scenario may tighten/loosen)
DTI (Debt-to-Income) <= 35% by default
"""
from __future__ import annotations

import random
from typing import Optional

from .base import BaseAgent
from ..environment import NATIONAL_ANNUAL_INCOME


class BankAgent(BaseAgent):
    agent_type = "bank"

    def __init__(self, unique_id: int, model, **kwargs):
        super().__init__(unique_id, model, **kwargs)
        self.loans_approved: int   = 0
        self.loans_rejected: int   = 0
        self.total_lent:     float = 0.0
        self.base_ltv:       float = 0.80
        self.base_dti:       float = 0.35
        # Each bank instance has slightly different risk appetite
        self.risk_tolerance: float = random.uniform(0.85, 1.15)

    # ------------------------------------------------------------------
    def _evaluate_application(
        self,
        property_value: float,
        loan_amount:    float,
        annual_income:  float,
        scenario_params: dict,
    ) -> bool:
        bct_rate   = scenario_params.get("bct_rate", 0.08)
        credit_rate = scenario_params.get("credit_approval_rate", 0.55)

        # LTV check
        ltv = loan_amount / max(1, property_value)
        ltv_limit = self.base_ltv * self.risk_tolerance
        if bct_rate > 0.10:
            ltv_limit *= 0.90  # tighten when rates high
        if ltv > ltv_limit:
            return False

        # DTI check (annual mortgage payment ≈ loan * bct_rate)
        annual_payment = loan_amount * bct_rate
        dti            = annual_payment / max(1, annual_income)
        dti_limit      = self.base_dti * self.risk_tolerance
        if dti > dti_limit:
            return False

        # Scenario base credit approval probability
        if random.random() > credit_rate * self.risk_tolerance:
            return False

        return True

    # ------------------------------------------------------------------
    def step(self, market_state: dict, scenario_params: dict) -> list:
        if not self.is_active:
            return []

        actions = []
        applications: list = market_state.get("mortgage_queue", [])

        # Process a batch of applications
        batch_size = max(5, int(len(applications) * 0.30))
        batch = applications[:batch_size]

        for app in batch:
            property_value = app.get("property_value", 200_000)
            down_payment   = app.get("down_payment",    40_000)
            loan_amount    = property_value - down_payment
            annual_income  = app.get("annual_income", NATIONAL_ANNUAL_INCOME)

            approved = self._evaluate_application(
                property_value=property_value,
                loan_amount=loan_amount,
                annual_income=annual_income,
                scenario_params=scenario_params,
            )

            app["approved"]    = approved
            app["bank_id"]     = self.agent_id

            if approved:
                self.loans_approved += 1
                self.total_lent     += loan_amount
                self.record_action(True, utility_delta=loan_amount * 0.002)
            else:
                self.loans_rejected += 1
                self.record_action(False)

            actions.append({
                "type":         "mortgage_decision",
                "buyer_id":     app.get("buyer_id", ""),
                "approved":     approved,
                "loan_amount":  round(loan_amount, 2),
                "property_value": round(property_value, 2),
            })

        # Remove processed applications
        del applications[:batch_size]

        return actions
