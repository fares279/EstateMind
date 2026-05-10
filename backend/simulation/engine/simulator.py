"""
TunisiaRealEstateSimulator — thin orchestration wrapper around TunisiaMarketModel.

Responsibilities:
  1. Create the Mesa model
  2. Drive model.step() for num_months iterations
  3. Persist progress to the SimulationRun Django model after each step
  4. Finalise and save results on completion or error
"""
from __future__ import annotations

import logging

logger = logging.getLogger("simulation.simulator")


class TunisiaRealEstateSimulator:
    """
    Runs a TunisiaMarketModel and saves results to the Django DB.
    Intended to execute inside a background daemon thread.

    Usage::

        sim = TunisiaRealEstateSimulator(run_id, scenario_name, num_months, agent_scale)
        sim.run()
    """

    def __init__(
        self,
        run_id: str,
        scenario_name: str,
        num_months: int,
        agent_scale: str,
        seed: int = 2026,
        policy_overrides: dict | None = None,
    ) -> None:
        from .model import TunisiaMarketModel

        self.run_id = str(run_id)
        self.model  = TunisiaMarketModel(
            scenario_name    = scenario_name,
            num_months       = num_months,
            agent_scale      = agent_scale,
            seed             = seed,
            policy_overrides = policy_overrides or {},
        )

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Execute the full simulation, persisting progress to DB."""
        from ..models          import SimulationRun
        from django.utils      import timezone
        from django.db         import connections

        monthly_states: list = []

        try:
            run = SimulationRun.objects.get(run_id=self.run_id)
            run.status     = SimulationRun.STATUS_RUNNING
            run.started_at = timezone.now()
            run.save(update_fields=["status", "started_at", "updated_at"])

            for _month in range(self.model.num_months):
                state = self.model.step()
                monthly_states.append(state)

                # Live progress persisted after each month
                run.current_month         = self.model.current_month
                run.total_transactions    = len(self.model.all_transactions)
                if self.model.all_transactions:
                    recent = self.model.all_transactions[-20:]
                    run.avg_transaction_price = sum(
                        t.get("total_price", 0) for t in recent
                    ) / len(recent)
                run.save(update_fields=[
                    "current_month", "total_transactions",
                    "avg_transaction_price", "updated_at",
                ])

            # Finalise
            run.monthly_states = monthly_states
            run.agent_outcomes = self.model.agent_outcomes()
            run.final_metrics  = self.model.final_metrics(monthly_states)
            run.status         = SimulationRun.STATUS_COMPLETE
            run.completed_at   = timezone.now()
            run.save()

        except Exception as exc:
            logger.exception("Simulation %s crashed", self.run_id)
            try:
                run = SimulationRun.objects.get(run_id=self.run_id)
                run.status        = SimulationRun.STATUS_ERROR
                run.error_message = str(exc)
                run.save(update_fields=["status", "error_message", "updated_at"])
            except Exception:
                pass
        finally:
            connections.close_all()
