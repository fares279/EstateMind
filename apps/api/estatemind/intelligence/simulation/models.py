"""
SimulationRun — persists the state of one multi-agent simulation run.
AgentCalibrationProfile — stores calibrated agent reward weights.

Module 10 Models for hardening requirements:
1. Inverse RL calibration: AgentCalibrationProfile
2. Scenario validation: stored in SimulationRun.validation_result
3. Stochastic testing: stored in SimulationRun stochastic_tests
4. Ensemble output: SimulationRun.ensemble_output
5. RL feedback: SimulationRun.rl_policy_test_results
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import date


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

    # Basic identification
    run_id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Who started the run; runs without an owner (older ones) can only be deleted by staff
    owner                 = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                              on_delete=models.SET_NULL, related_name='simulation_runs')
    user                  = models.ForeignKey(settings.AUTH_USER_MODEL,
                                             on_delete=models.SET_NULL, null=True, blank=True)
    
    # Original fields (preserved for backward compatibility)
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
    
    # Scenario configuration & validation
    scenario_type         = models.CharField(max_length=50, null=True, blank=True)
    # E.g., "baseline", "interest_rate_shock", "policy_intervention"
    
    scenario_config       = models.JSONField(null=True, blank=True)
    # Full scenario parameters submitted by user
    
    validation_result     = models.JSONField(null=True, blank=True)
    # Stores ScenarioValidator output (errors, warnings, feasibility_score)
    
    # Ensemble execution
    n_runs                = models.IntegerField(default=1)
    n_agents              = models.IntegerField(default=500)
    seed_base             = models.IntegerField(default=42)
    
    ensemble_output       = models.JSONField(null=True, blank=True)
    # Full quantile bands, probability distributions, agent outcomes
    
    # Stochastic testing results
    stochastic_tests      = models.JSONField(null=True, blank=True)
    # Reproducibility, variance, and calibration test results
    
    reproducibility_passed = models.BooleanField(null=True, blank=True)
    variance_cv           = models.FloatField(null=True, blank=True)
    calibration_mape      = models.FloatField(null=True, blank=True)
    calibration_quality   = models.CharField(max_length=20, null=True, blank=True)
    # E.g., "GOOD", "ACCEPTABLE", "POOR"
    
    # RL Policy feedback loop
    rl_policy_test_results = models.JSONField(null=True, blank=True)
    # Strategy comparison, policy assessment, recommendation
    
    # Async task tracking
    celery_task_id        = models.CharField(max_length=255, null=True, blank=True)
    
    # Timestamps
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
            models.Index(fields=["user", "status"]),
            models.Index(fields=["scenario_type", "completed_at"]),
        ]

    def __str__(self):
        return f"SimulationRun({self.run_id}) scenario={self.scenario_name} status={self.status}"


class AgentCalibrationProfile(models.Model):
    """
    Stores calibrated agent reward function weights.
    
    One profile per agent type per calibration date.
    Only active=True profiles are used in simulations.
    """
    
    AGENT_TYPES = [
        ('buyer', 'Buyer Agent'),
        ('seller', 'Seller Agent'),
        ('developer', 'Developer Agent'),
        ('speculator', 'Speculator Agent'),
    ]
    
    CALIBRATION_QUALITY_CHOICES = [
        ('GOOD', 'Well-calibrated (Good)'),
        ('ACCEPTABLE', 'Acceptable'),
        ('POOR', 'Miscalibrated (Poor)'),
    ]
    
    agent_type            = models.CharField(max_length=20, choices=AGENT_TYPES)
    calibration_date      = models.DateField(default=date.today, db_index=True)
    is_active             = models.BooleanField(default=True, db_index=True)
    
    # Calibrated reward function weights (inverse RL output)
    reward_weights        = models.JSONField()
    # E.g., {
    #   'rental_yield_weight': 0.25,
    #   'appreciation_weight': 0.35,
    #   'holding_cost_weight': 0.15,
    #   'risk_aversion_weight': 0.15,
    #   'budget_constraint_weight': 0.10,
    # }
    
    # Calibration quality metrics
    directional_accuracy  = models.FloatField()
    # % of historical periods where direction matched (target: 80%+)
    
    mean_price_mape       = models.FloatField()
    # Mean absolute percentage error vs historical (target: <10%)
    
    calibration_quality   = models.CharField(max_length=20,
                                            choices=CALIBRATION_QUALITY_CHOICES)
    
    # Training data metadata
    training_transactions = models.IntegerField()
    training_date_range_start = models.DateField()
    training_date_range_end = models.DateField()
    
    # Calibration method
    calibration_method   = models.CharField(max_length=50)
    # E.g., "inverse_rl_mle", "prior_based", "literature_derived"
    
    notes                 = models.TextField(blank=True)
    
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Agent Calibration Profile'
        verbose_name_plural = 'Agent Calibration Profiles'
        ordering = ['-calibration_date', 'agent_type']
        indexes = [
            models.Index(fields=['agent_type', 'is_active']),
            models.Index(fields=['calibration_date', 'is_active']),
        ]
        unique_together = [['agent_type', 'calibration_date']]
        # Only one profile per agent type per date
    
    def __str__(self):
        return (f"AgentCalibrationProfile({self.agent_type}) "
               f"{self.calibration_date} quality={self.calibration_quality}")
    
    @classmethod
    def get_active_profile(cls, agent_type: str):
        """Returns currently active calibration for given agent type."""
        return cls.objects.filter(
            agent_type=agent_type,
            is_active=True
        ).latest('calibration_date')
    
    @classmethod
    def activate_profile(cls, profile_id: int):
        """
        Deactivates all profiles for this agent type,
        then activates the specified one.
        """
        profile = cls.objects.get(id=profile_id)
        cls.objects.filter(agent_type=profile.agent_type).update(is_active=False)
        profile.is_active = True
        profile.save()
