"""
Price forecast models — separated from the valuation app.
DelegationForecast  : 12-month price trajectory per delegation × property type.
DelegationPriceData : Current market snapshot per delegation × property type.
"""
from django.db import models


_PROP_CHOICES = [
    ('apartment',  'Apartment'),
    ('house',      'House'),
    ('commercial', 'Commercial'),
    ('land',       'Land'),
]


class DelegationPriceData(models.Model):
    """
    Current market price data per delegation × property type.
    Sourced from delegations.csv; populated by generate_forecasts command.
    All prices in TND/m².
    """
    delegation_name  = models.CharField(max_length=255, db_index=True)
    governorate      = models.CharField(max_length=100, db_index=True)
    property_type    = models.CharField(max_length=20, choices=_PROP_CHOICES, db_index=True)
    price_min        = models.FloatField()
    price_avg        = models.FloatField()
    price_max        = models.FloatField()
    annual_trend_pct = models.FloatField()
    notes            = models.TextField(blank=True)

    class Meta:
        unique_together = ('delegation_name', 'governorate', 'property_type')
        ordering = ['governorate', 'delegation_name', 'property_type']
        verbose_name = 'Delegation Price Data'
        verbose_name_plural = 'Delegation Price Data'
        indexes = [
            models.Index(fields=['governorate', 'property_type']),
            models.Index(fields=['property_type', 'price_avg']),
        ]

    def __str__(self):
        return f"{self.delegation_name} [{self.property_type}]: {self.price_avg} TND/m²"


class DelegationForecast(models.Model):
    """
    12-month ahead price-per-m² forecast per delegation × property type.
    Raw values stored in millimes (1 TND = 1 000 millimes).
    Divide predicted_price_per_m2 / 1 000 when displaying TND.
    """
    delegation_name        = models.CharField(max_length=255, db_index=True)
    governorate            = models.CharField(max_length=100, db_index=True, blank=True)
    property_type          = models.CharField(max_length=20, choices=_PROP_CHOICES, default='apartment', db_index=True)
    forecast_origin        = models.DateField()
    forecast_month         = models.DateField()
    horizon_idx            = models.IntegerField()        # 1–12
    predicted_price_per_m2 = models.FloatField()          # millimes; ÷1 000 = TND/m²
    # measured forecast error; None when not measured (it used to default to a constant 2.5%)
    model_mape_pct         = models.FloatField(null=True, blank=True, default=None)
    model_version          = models.CharField(max_length=50, default='csv_v2')
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('delegation_name', 'governorate', 'forecast_origin', 'horizon_idx', 'property_type')
        ordering = ['delegation_name', 'property_type', 'horizon_idx']
        verbose_name = 'Delegation Forecast'
        verbose_name_plural = 'Delegation Forecasts'
        indexes = [
            models.Index(fields=['delegation_name', 'forecast_origin', 'property_type']),
            models.Index(fields=['governorate', 'horizon_idx', 'property_type']),
            models.Index(fields=['property_type', 'horizon_idx']),
        ]

    def __str__(self):
        tnd = self.predicted_price_per_m2 / 1000
        return f"{self.delegation_name} [{self.property_type}] {self.forecast_month}: {tnd:,.0f} TND/m²"


class ForecastModelVersion(models.Model):
    """
    Registry of forecast models trained for each delegation × property type.
    Tracks:
      - Which model type (linear trend, N-BEATS, TFT) is in use
      - Backtest metrics (median MAPE, p90 MAPE, regime shift windows)
      - Conformal predictor calibration parameters
      - Retraining history and reasons

    Every forecast request queries this table to determine which model to use.
    """
    delegation_name = models.CharField(max_length=255, db_index=True)
    governorate     = models.CharField(max_length=100, blank=True)
    property_type   = models.CharField(max_length=20, choices=_PROP_CHOICES, db_index=True)

    # Model identity
    model_type      = models.CharField(
        max_length=50,
        choices=[
            ('linear_trend', 'Linear Trend'),
            ('nbeats', 'N-BEATS'),
            ('tft', 'Temporal Fusion Transformer'),
        ],
        default='linear_trend',
    )
    history_months  = models.IntegerField()  # How many months of history were used to train

    # Backtest metrics
    median_mape     = models.FloatField(null=True, blank=True)  # % error, median window
    p90_mape        = models.FloatField(null=True, blank=True)  # 90th percentile MAPE
    max_mape        = models.FloatField(null=True, blank=True)  # worst-case MAPE
    n_backtest_windows = models.IntegerField(default=0)        # number of rolling windows tested
    regime_shift_windows = models.JSONField(default=list, blank=True)  # indices where MAPE spiked

    # Conformal predictor calibration (learned from backtest residuals)
    conformal_quantile = models.FloatField(null=True, blank=True)  # band half-width in price units
    conformal_coverage = models.FloatField(default=0.90)           # coverage level (e.g. 90%)
    conformal_n_calibration = models.IntegerField(default=0)       # samples used to calibrate

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('champion', 'In production'),
            ('challenger', 'Testing'),
            ('retired', 'Replaced'),
        ],
        default='champion',
    )
    is_active = models.BooleanField(default=True)  # Only one active model per delegation×property_type

    # Audit trail
    retrain_reason = models.TextField(blank=True)  # Why this model was retrained
    qualified = models.BooleanField(default=False)  # median_mape < MAPE_THRESHOLD
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('delegation_name', 'property_type', 'status')
        ordering = ['-created_at']
        verbose_name = 'Forecast Model Version'
        verbose_name_plural = 'Forecast Model Versions'
        indexes = [
            models.Index(fields=['delegation_name', 'property_type', 'is_active']),
            models.Index(fields=['model_type', 'qualified']),
        ]

    def __str__(self):
        mape_str = f"{self.median_mape:.1f}%" if self.median_mape else "unknown"
        return (f"{self.delegation_name} [{self.property_type}] "
                f"{self.model_type} (MAPE: {mape_str})")
