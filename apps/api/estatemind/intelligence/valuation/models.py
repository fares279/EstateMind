import uuid

from django.conf import settings
from django.db import models


class ValuationRequest(models.Model):
    """Persisted valuation request and valuation response history."""

    PROPERTY_TYPES = [
        ('apartment', 'Apartment'), ('house', 'House'), ('villa', 'Villa'),
        ('land', 'Land'), ('commercial', 'Commercial'), ('office', 'Office'),
        ('farm', 'Farm'),
    ]
    TRANSACTION_TYPES = [('sale', 'Sale'), ('rent', 'Rent')]
    CONDITION_CHOICES = [
        ('new', 'New'), ('excellent', 'Excellent'), ('good', 'Good'),
        ('fair', 'Fair'), ('needs_renovation', 'Needs Renovation'),
    ]

    user             = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='valuation_requests',
    )
    property_type    = models.CharField(max_length=20, choices=PROPERTY_TYPES)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, default='sale')
    governorate      = models.CharField(max_length=100, blank=True)
    city             = models.CharField(max_length=100, blank=True)
    neighborhood     = models.CharField(max_length=100, blank=True)
    size_m2          = models.FloatField(null=True, blank=True)
    bedrooms         = models.IntegerField(null=True, blank=True)
    bathrooms        = models.IntegerField(null=True, blank=True)
    condition        = models.CharField(max_length=30, blank=True)
    has_pool         = models.BooleanField(default=False)
    has_garden       = models.BooleanField(default=False)
    has_parking      = models.BooleanField(default=False)
    sea_view         = models.BooleanField(default=False)
    elevator         = models.BooleanField(default=False)
    description      = models.TextField(blank=True)
    image_count      = models.IntegerField(default=0)

    # Results
    estimated_price  = models.FloatField()
    lower_bound      = models.FloatField()
    upper_bound      = models.FloatField()
    price_per_m2     = models.FloatField(null=True, blank=True)
    confidence       = models.IntegerField(default=50)
    confidence_level = models.CharField(max_length=20, default='Medium')
    prediction_mode  = models.CharField(max_length=50, default='heuristic')
    response_data    = models.JSONField(default=dict)

    # Model provenance
    model_name       = models.CharField(max_length=80, blank=True)
    model_version    = models.CharField(max_length=20, blank=True)
    model_artifact   = models.CharField(max_length=255, blank=True)

    # Climate signals
    climate_risk_category   = models.CharField(max_length=15, blank=True)
    climate_adjustment_pct  = models.FloatField(null=True, blank=True)
    climate_adjusted_price  = models.FloatField(null=True, blank=True)
    climate_label           = models.CharField(max_length=60, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.property_type} – {self.governorate} – {self.estimated_price:,.0f} TND"


class ValuationModelVersion(models.Model):
    STATUS_CHOICES = [
        ('training', 'Training'),
        ('challenger', 'Challenger — A/B testing'),
        ('champion', 'Champion — 100% traffic'),
        ('retired', 'Retired — replaced'),
        ('failed', 'Failed — rejected'),
    ]

    model_name = models.CharField(max_length=80)
    version = models.CharField(max_length=20)
    artifact_path = models.CharField(max_length=255)
    training_date = models.DateField()
    training_data_hash = models.CharField(max_length=64)
    training_samples = models.IntegerField(default=0)

    eval_rmse = models.FloatField(default=0)
    eval_r2 = models.FloatField(default=0)
    eval_mape = models.FloatField(default=0)
    eval_holdout_size = models.IntegerField(default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='training')
    ab_traffic_pct = models.IntegerField(default=0)
    promoted_by = models.CharField(max_length=80, blank=True)
    promoted_at = models.DateTimeField(null=True, blank=True)
    calibration_profile = models.JSONField(default=dict, blank=True)
    drift_profile = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('model_name', 'version')

    def __str__(self):
        return f"{self.model_name} v{self.version} [{self.status}]"


class ValuationPredictionLog(models.Model):
    request_id = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    model_version = models.ForeignKey(ValuationModelVersion, on_delete=models.SET_NULL, null=True, blank=True)
    model_name = models.CharField(max_length=80, blank=True)
    model_version_label = models.CharField(max_length=20, blank=True)
    input_hash = models.CharField(max_length=64)
    input_features = models.JSONField(default=dict)
    prediction_tnd = models.FloatField()
    confidence_low = models.FloatField()
    confidence_high = models.FloatField()
    confidence_level = models.CharField(max_length=10)
    fallback_used = models.BooleanField(default=False)
    latency_ms = models.IntegerField(default=0)
    snapshot_date = models.DateField(null=True, blank=True)
    actual_tnd = models.FloatField(null=True, blank=True)
    actual_recorded_at = models.DateTimeField(null=True, blank=True)
    calibration_state = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['model_version', 'created_at']),
            models.Index(fields=['model_name', 'created_at']),
        ]

    def __str__(self):
        version = self.model_version_label or (self.model_version.version if self.model_version_id else 'unknown')
        return f"Prediction {self.request_id} [{version}]"
