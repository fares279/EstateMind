"""
SimulationRun — persists the state of one multi-agent simulation run.
"""
import uuid
from django.db import models


class SimulationRun(models.Model):
    STATUS_PENDING  = "pending"
    STATUS_RUNNING  = "running"
    STATUS_COMPLETE = "complete"
    STATUS_ERROR    = "error"

    STATUS_CHOICES = [
        (STATUS_PENDING,  "Pending"),
        (STATUS_RUNNING,  "Running"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_ERROR,    "Error"),
    ]

    run_id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario_name         = models.CharField(max_length=64, db_index=True)
    agent_scale           = models.CharField(max_length=16, default="tiny")
    num_months            = models.PositiveSmallIntegerField(default=12)
    status                = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    current_month         = models.PositiveSmallIntegerField(default=0)
    total_transactions    = models.PositiveIntegerField(default=0)
    avg_transaction_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    monthly_states        = models.JSONField(default=list)
    agent_outcomes        = models.JSONField(default=list)
    final_metrics         = models.JSONField(default=dict)
    error_message         = models.TextField(blank=True, default="")
    created_at            = models.DateTimeField(auto_now_add=True)
    started_at            = models.DateTimeField(null=True, blank=True)
    completed_at          = models.DateTimeField(null=True, blank=True)
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = 'Simulation Run'
        verbose_name_plural = 'Simulation Runs'
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["scenario_name", "created_at"]),
        ]

    def __str__(self):
        return f"SimulationRun({self.run_id}) scenario={self.scenario_name} status={self.status}"
