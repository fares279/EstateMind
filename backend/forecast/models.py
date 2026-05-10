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
    model_mape_pct         = models.FloatField(default=2.50)
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
