"""Core app - Shared models and utilities"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Region(models.Model):
    """Tunisia's 24 governorates with market metadata"""
    governorate = models.CharField(max_length=100, unique=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)
    avg_price_per_sqm = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['governorate']

    def __str__(self):
        return self.governorate


class Delegation(models.Model):
    """Administrative delegation under a governorate (Region)."""
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='delegations')
    name = models.CharField(max_length=255)
    population = models.IntegerField(default=0)
    centroid_lat = models.FloatField(null=True, blank=True)
    centroid_lon = models.FloatField(null=True, blank=True)
    geojson_polygon = models.JSONField(null=True, blank=True)
    is_coastal = models.BooleanField(default=False)

    # ── Market benchmarks (TND/m²) — sourced from delegations.csv ──────────
    apt_min_tnd     = models.FloatField(null=True, blank=True, verbose_name='Apt Min (TND/m²)')
    apt_avg_tnd     = models.FloatField(null=True, blank=True, verbose_name='Apt Avg (TND/m²)')
    apt_max_tnd     = models.FloatField(null=True, blank=True, verbose_name='Apt Max (TND/m²)')
    apt_trend_pct   = models.FloatField(null=True, blank=True, verbose_name='Apt Trend %')
    house_min_tnd   = models.FloatField(null=True, blank=True, verbose_name='House Min (TND/m²)')
    house_avg_tnd   = models.FloatField(null=True, blank=True, verbose_name='House Avg (TND/m²)')
    house_max_tnd   = models.FloatField(null=True, blank=True, verbose_name='House Max (TND/m²)')
    house_trend_pct = models.FloatField(null=True, blank=True, verbose_name='House Trend %')
    comm_min_tnd    = models.FloatField(null=True, blank=True, verbose_name='Comm Min (TND/m²)')
    comm_avg_tnd    = models.FloatField(null=True, blank=True, verbose_name='Comm Avg (TND/m²)')
    comm_max_tnd    = models.FloatField(null=True, blank=True, verbose_name='Comm Max (TND/m²)')
    comm_trend_pct  = models.FloatField(null=True, blank=True, verbose_name='Comm Trend %')
    land_min_tnd    = models.FloatField(null=True, blank=True, verbose_name='Land Min (TND/m²)')
    land_avg_tnd    = models.FloatField(null=True, blank=True, verbose_name='Land Avg (TND/m²)')
    land_max_tnd    = models.FloatField(null=True, blank=True, verbose_name='Land Max (TND/m²)')
    land_trend_pct  = models.FloatField(null=True, blank=True, verbose_name='Land Trend %')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('region', 'name')
        ordering = ['region__governorate', 'name']
        verbose_name = 'Delegation'
        verbose_name_plural = 'Delegations'

    def __str__(self):
        return f"{self.name} — {self.region.governorate}"


class TimeSeriesBase(models.Model):
    """Base class for all time-series data"""
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['-date']


class Property(models.Model):
    """Core property listing (Real-Time Scraping)"""
    PROPERTY_TYPES = [
        ('apartment',  'Apartment'),
        ('house',      'House'),
        ('commercial', 'Commercial'),
        ('land',       'Land'),
    ]
    TRANSACTION_TYPES = [
        ('sale', 'Sale'),
        ('rent', 'Rent'),
    ]

    external_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, default='sale')
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True)
    delegation = models.ForeignKey(Delegation, on_delete=models.SET_NULL, null=True, blank=True)
    price = models.FloatField()
    area_sqm = models.FloatField()
    price_per_sqm = models.FloatField(null=True, blank=True)
    rooms = models.IntegerField(null=True, blank=True)
    bedrooms = models.IntegerField(null=True, blank=True)
    bathrooms = models.IntegerField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    image_url = models.URLField(null=True, blank=True)
    location_raw = models.CharField(max_length=255, blank=True, default='')
    source = models.CharField(max_length=100)  # Which platform scraped from
    currency = models.CharField(max_length=10, default='TND')
    posted_at = models.DateTimeField(null=True, blank=True)
    scraped_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name_plural = 'Properties'
        indexes = [
            models.Index(fields=['region', 'property_type']),
            models.Index(fields=['delegation', 'transaction_type']),
            models.Index(fields=['posted_at']),
        ]

    def __str__(self):
        delegation_name = self.delegation.name if self.delegation else "Unknown"
        return f"{self.title} ({delegation_name})"


class Valuation(models.Model):
    """AI Price Prediction"""
    property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name='valuation')
    predicted_price = models.FloatField()
    mape_confidence = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    comparable_count = models.IntegerField(default=0)
    model_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Valuation: {self.property.title}"


class PriceTrend(TimeSeriesBase):
    """Price Trend Forecasting"""
    property_type = models.CharField(max_length=20)
    avg_price = models.FloatField()
    trend_direction = models.CharField(max_length=10)  # Up, Down, Stable
    forecast_3m = models.FloatField(null=True, blank=True)
    forecast_6m = models.FloatField(null=True, blank=True)
    forecast_12m = models.FloatField(null=True, blank=True)


class ClimateRisk(models.Model):
    """
    Climate Intelligence Layer.
    One record per Region (governorate). Populated by load_climate_data management command
    from the curated CSV dataset + Open-Meteo baseline. Used by the valuation engine
    (price adjustment) and the Climate Intelligence frontend tab.
    """
    RISK_LEVELS = [
        ('low', 'Low'), ('medium', 'Medium'),
        ('high', 'High'), ('very_high', 'Very High'),
    ]
    RISK_CATEGORIES = [
        ('Low', 'Low'), ('Moderate', 'Moderate'),
        ('High', 'High'), ('Very High', 'Very High'),
    ]
    GRADES = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('F', 'F')]

    region = models.OneToOneField(Region, on_delete=models.CASCADE, related_name='climate_risk')

    # ── Risk levels (categorical) ─────────────────────────────────────────
    flood_risk       = models.CharField(max_length=10, choices=RISK_LEVELS, default='medium')
    heat_stress_risk = models.CharField(max_length=10, choices=RISK_LEVELS, default='medium')
    drought_risk     = models.CharField(max_length=10, choices=RISK_LEVELS, default='medium')
    earthquake_risk  = models.CharField(max_length=10, choices=RISK_LEVELS, default='low')

    # ── Numeric risk scores (0–100 scale from the dataset) ───────────────
    flood_risk_score     = models.FloatField(null=True, blank=True)
    heat_risk_score      = models.FloatField(null=True, blank=True)
    drought_risk_score   = models.FloatField(null=True, blank=True)
    earthquake_risk_score = models.FloatField(null=True, blank=True)

    # ── Composite scores ─────────────────────────────────────────────────
    combined_risk_score = models.FloatField(null=True, blank=True)   # weighted 0–10
    risk_category       = models.CharField(max_length=15, choices=RISK_CATEGORIES, default='Moderate')

    # ── Sustainability & liveability ──────────────────────────────────────
    sustainability_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)], default=50,
    )
    sustainability_grade  = models.CharField(max_length=2, choices=GRADES, default='C')
    livability_score      = models.FloatField(null=True, blank=True)
    infrastructure_score  = models.FloatField(null=True, blank=True)

    # ── Geospatial context ────────────────────────────────────────────────
    lat            = models.FloatField(null=True, blank=True)
    lon            = models.FloatField(null=True, blank=True)
    is_coastal     = models.BooleanField(default=False)
    climate_region = models.CharField(max_length=30, blank=True)  # e.g. North, South-East

    # ── Climate baseline metrics ──────────────────────────────────────────
    avg_temp_c          = models.FloatField(null=True, blank=True)
    max_summer_temp_c   = models.FloatField(null=True, blank=True)
    avg_rainfall_mm     = models.FloatField(null=True, blank=True)
    days_above_35c      = models.IntegerField(null=True, blank=True)
    sea_level_exposure  = models.CharField(max_length=10, blank=True)

    # ── Climate-driven price impact ───────────────────────────────────────
    price_adjustment_pct = models.FloatField(null=True, blank=True)  # e.g. -8.5 or +3.5

    # ── Scenario projections ─────────────────────────────────────────────
    scenario_baseline = models.FloatField(null=True, blank=True)  # sustainability today
    scenario_2c       = models.FloatField(null=True, blank=True)  # at +2 °C warming
    scenario_4c       = models.FloatField(null=True, blank=True)  # at +4 °C warming

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Climate Risk Assessment'
        verbose_name_plural = 'Climate Risk Assessments'

    def __str__(self):
        return f"Climate Risk: {self.region.governorate} — {self.risk_category}"


class DelegationMarketSnapshot(models.Model):
    """Latest or historical derived market metrics for one delegation."""

    delegation = models.ForeignKey(
        Delegation,
        on_delete=models.CASCADE,
        related_name='market_snapshots',
    )
    as_of_date = models.DateField()
    listing_count = models.IntegerField(default=0)
    sale_listing_count = models.IntegerField(default=0)
    rent_listing_count = models.IntegerField(default=0)
    median_sale_price = models.FloatField(null=True, blank=True)
    median_rent_price = models.FloatField(null=True, blank=True)
    avg_sale_price = models.FloatField(null=True, blank=True)
    avg_rent_price = models.FloatField(null=True, blank=True)
    median_price_per_sqm = models.FloatField(null=True, blank=True)
    price_per_sqm_distribution = models.JSONField(default=dict, blank=True)
    supply_pressure = models.FloatField(default=0)
    median_days_on_market = models.FloatField(null=True, blank=True)
    climate_risk_level = models.CharField(max_length=10, blank=True, default='')
    heat_risk_level = models.CharField(max_length=10, blank=True, default='')
    sustainability_score = models.FloatField(null=True, blank=True)
    trend_direction = models.CharField(max_length=10, blank=True, default='')
    forecast_3m = models.FloatField(null=True, blank=True)
    forecast_6m = models.FloatField(null=True, blank=True)
    forecast_12m = models.FloatField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['delegation__region__governorate', 'delegation__name', '-as_of_date']
        constraints = [
            models.UniqueConstraint(
                fields=['delegation', 'as_of_date'],
                name='unique_snapshot_per_delegation_date',
            )
        ]

    def __str__(self):
        return f"{self.delegation} snapshot @ {self.as_of_date}"


class DelegationMarketSegment(models.Model):
    """Segmented market metrics by delegation, property type, and transaction type."""

    snapshot = models.ForeignKey(
        DelegationMarketSnapshot,
        on_delete=models.CASCADE,
        related_name='segments',
    )
    property_type = models.CharField(max_length=20, default='all')
    transaction_type = models.CharField(max_length=10, choices=Property.TRANSACTION_TYPES)
    listing_count = models.IntegerField(default=0)
    median_price = models.FloatField(null=True, blank=True)
    avg_price = models.FloatField(null=True, blank=True)
    median_price_per_sqm = models.FloatField(null=True, blank=True)
    avg_price_per_sqm = models.FloatField(null=True, blank=True)
    min_price = models.FloatField(null=True, blank=True)
    max_price = models.FloatField(null=True, blank=True)
    avg_surface_sqm = models.FloatField(null=True, blank=True)
    median_surface_sqm = models.FloatField(null=True, blank=True)
    median_days_on_market = models.FloatField(null=True, blank=True)
    trend_direction = models.CharField(max_length=10, blank=True, default='')
    forecast_3m = models.FloatField(null=True, blank=True)
    forecast_6m = models.FloatField(null=True, blank=True)
    forecast_12m = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['snapshot__delegation__name', 'property_type', 'transaction_type']
        constraints = [
            models.UniqueConstraint(
                fields=['snapshot', 'property_type', 'transaction_type'],
                name='unique_market_segment_per_snapshot',
            )
        ]

    def __str__(self):
        return f"{self.snapshot.delegation} {self.property_type}/{self.transaction_type}"
