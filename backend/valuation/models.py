from django.db import models
from django.conf import settings


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


class DelegationForecast(models.Model):
    """
    12-month ahead price-per-m2 forecast per Tunisian delegation.
    Raw values stored in millimes (1 TND = 1000 millimes).
    Always divide predicted_price_per_m2 by 1000 when displaying TND.
    """
    delegation_name        = models.CharField(max_length=255, db_index=True)
    governorate            = models.CharField(max_length=100, db_index=True, blank=True)
    delegation_fk          = models.ForeignKey(
        'core.Delegation', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='forecasts',
    )
    forecast_origin        = models.DateField()
    forecast_month         = models.DateField()
    horizon_idx            = models.IntegerField()   # 1–12
    predicted_price_per_m2 = models.FloatField()     # millimes; ÷1000 = TND/m²
    model_mape_pct         = models.FloatField(default=2.92)
    model_version          = models.CharField(max_length=50, default='h12_v1')
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('delegation_name', 'forecast_origin', 'horizon_idx')
        ordering        = ['delegation_name', 'horizon_idx']
        indexes = [
            models.Index(fields=['delegation_name', 'forecast_origin']),
            models.Index(fields=['governorate', 'horizon_idx']),
            models.Index(fields=['governorate', 'forecast_origin']),
        ]

    def __str__(self):
        tnd = self.predicted_price_per_m2 / 1000
        return f"{self.delegation_name} {self.forecast_month}: {tnd:,.0f} TND/m2"
