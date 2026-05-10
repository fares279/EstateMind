from django.db import models
from django.conf import settings


PROPERTY_TYPE_CHOICES = [
    ('apartment', 'Apartment'),
    ('house', 'House'),
    ('commercial', 'Commercial'),
    ('land', 'Land'),
]

GOVERNORATES = [
    'Ariana', 'Béja', 'Ben Arous', 'Bizerte', 'Gabès', 'Gafsa', 'Jendouba',
    'Kairouan', 'Kasserine', 'Kébili', 'La Manouba', 'Le Kef', 'Mahdia',
    'Médenine', 'Monastir', 'Nabeul', 'Sfax', 'Sidi Bouzid', 'Siliana',
    'Sousse', 'Tataouine', 'Tozeur', 'Tunis', 'Zaghouan',
]


class PortfolioAsset(models.Model):
    PROPERTY_TYPES = PROPERTY_TYPE_CHOICES

    user                    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='investor_portfolio_assets',
    )
    property_name           = models.CharField(max_length=200)
    property_type           = models.CharField(max_length=20, choices=PROPERTY_TYPES, default='apartment')
    governorate             = models.CharField(max_length=100)
    delegation              = models.CharField(max_length=100)
    surface_m2              = models.FloatField()
    room_count              = models.IntegerField(default=3)
    floor_level             = models.IntegerField(default=0)
    amenity_score           = models.FloatField(default=1.0)

    acquisition_price_tnd   = models.FloatField()
    acquisition_date        = models.DateField()
    current_value_tnd       = models.FloatField(null=True, blank=True)

    is_rented               = models.BooleanField(default=False)
    monthly_rent_tnd        = models.FloatField(default=0.0)
    monthly_opex_tnd        = models.FloatField(default=0.0)

    notes                   = models.TextField(blank=True)
    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Portfolio Asset'
        verbose_name_plural = 'Portfolio Assets'

    def __str__(self):
        return f"{self.property_name} – {self.delegation}, {self.governorate}"

    @property
    def holding_days(self):
        from django.utils import timezone
        return (timezone.now().date() - self.acquisition_date).days

    @property
    def unrealized_gain_tnd(self):
        cv = self.current_value_tnd or self.acquisition_price_tnd
        return cv - self.acquisition_price_tnd

    @property
    def unrealized_gain_pct(self):
        if self.acquisition_price_tnd <= 0:
            return 0.0
        cv = self.current_value_tnd or self.acquisition_price_tnd
        return (cv - self.acquisition_price_tnd) / self.acquisition_price_tnd * 100


class ScanResult(models.Model):
    """Cached scanner result for a listing analysis."""
    user                    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='scan_results',
    )
    listing_price_tnd       = models.FloatField()
    surface_m2              = models.FloatField()
    property_type           = models.CharField(max_length=20)
    governorate             = models.CharField(max_length=100)
    delegation              = models.CharField(max_length=100)
    room_count              = models.IntegerField(default=3)

    # Model outputs
    undervaluation_label    = models.CharField(max_length=30, blank=True)
    undervaluation_proba    = models.FloatField(default=0.0)
    buy_signal              = models.CharField(max_length=20, blank=True)
    p_buy                   = models.FloatField(default=0.0)
    gross_yield_pct         = models.FloatField(default=0.0)
    opportunity_score       = models.FloatField(default=0.0)
    investment_grade        = models.CharField(max_length=5, blank=True)

    full_result             = models.JSONField(default=dict)
    created_at              = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Scan Result'
        verbose_name_plural = 'Scan Results'
