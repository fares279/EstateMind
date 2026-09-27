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


# ════════════════════════════════════════════════════════════════════════════════
# Module 7 Hardening: Model Registry, Calibration, Classifiers
# ════════════════════════════════════════════════════════════════════════════════

class InvestorScorerVersion(models.Model):
    """
    Tracks versions of all 7 investor scoring models.
    Supports champion/challenger promotion, A/B testing, and rollback.
    """
    SCORER_CHOICES = [
        ('undervaluation_detector', 'Undervaluation Detector'),
        ('yield_estimator', 'Yield Estimator'),
        ('buy_wait_classifier', 'Buy/Wait Classifier'),
        ('opportunity_scorer', 'Opportunity Scorer'),
        ('investment_grader', 'Investment Grader'),
        ('irr_calculator', 'IRR Calculator'),
        ('portfolio_risk_assessor', 'Portfolio Risk Assessor'),
    ]

    STATUS_CHOICES = [
        ('champion', 'Champion (Active)'),
        ('challenger', 'Challenger (Testing)'),
        ('retired', 'Retired'),
    ]

    AB_RESULT_CHOICES = [
        ('PENDING', 'Pending'),
        ('WINNER', 'Won A/B Test'),
        ('LOSER', 'Lost A/B Test'),
        ('INCONCLUSIVE', 'Inconclusive'),
    ]

    scorer_name             = models.CharField(max_length=50, choices=SCORER_CHOICES)
    version                 = models.CharField(max_length=20)  # "1.0", "1.1", "2.0"
    status                  = models.CharField(max_length=20, choices=STATUS_CHOICES, default='challenger')

    training_date           = models.DateTimeField()
    training_sample_count   = models.IntegerField()

    # Validation metrics (scorer-specific)
    validation_metric_primary = models.FloatField()
    validation_metric_primary_name = models.CharField(max_length=100)
    validation_metric_secondary = models.FloatField(null=True, blank=True)
    validation_metric_secondary_name = models.CharField(max_length=100, blank=True)

    # Deployment tracking
    promoted_at             = models.DateTimeField(null=True, blank=True)
    promoted_by             = models.CharField(max_length=100, blank=True)
    rollback_to_version     = models.CharField(max_length=20, null=True, blank=True)

    # A/B test configuration
    ab_test_active          = models.BooleanField(default=False)
    ab_test_traffic_pct     = models.FloatField(default=0.0)
    ab_test_start_date      = models.DateField(null=True, blank=True)
    ab_test_end_date        = models.DateField(null=True, blank=True)
    ab_test_result          = models.CharField(max_length=20, choices=AB_RESULT_CHOICES, default='PENDING')

    # Artifact storage
    artifact_path           = models.CharField(max_length=255)
    artifact_hash           = models.CharField(max_length=64)

    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('scorer_name', 'version')]
        verbose_name = 'Investor Scorer Version'
        verbose_name_plural = 'Investor Scorer Versions'

    def __str__(self):
        return f"{self.scorer_name} v{self.version} ({self.status})"


class CalibrationAuditRecord(models.Model):
    """
    Quarterly audit of investment grades against realized returns.
    Detects if grades are actually predictive (A > B > C > D by return).
    """
    STATUS_CHOICES = [
        ('PASS', 'Calibration OK'),
        ('WARN', 'Calibration Warning'),
        ('FAIL', 'Calibration Failed'),
        ('INSUFFICIENT_DATA', 'Not enough scored properties with a measurable return'),
    ]

    audit_date              = models.DateField()
    lookback_months         = models.IntegerField(default=6)

    # Per-grade statistics
    grade_a_count           = models.IntegerField(default=0)
    grade_a_mean_return     = models.FloatField(default=0.0)
    grade_a_std_return      = models.FloatField(default=0.0)

    grade_b_count           = models.IntegerField(default=0)
    grade_b_mean_return     = models.FloatField(default=0.0)
    grade_b_std_return      = models.FloatField(default=0.0)

    grade_c_count           = models.IntegerField(default=0)
    grade_c_mean_return     = models.FloatField(default=0.0)
    grade_c_std_return      = models.FloatField(default=0.0)

    grade_d_count           = models.IntegerField(default=0)
    grade_d_mean_return     = models.FloatField(default=0.0)
    grade_d_std_return      = models.FloatField(default=0.0)

    # Calibration status
    is_monotonic            = models.BooleanField(null=True, default=None)  # None: not determinable
    calibration_status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PASS')
    inversions_detected     = models.JSONField(default=list)  # e.g., ['B>A', 'C>B']

    # Recommended action
    recommended_action      = models.TextField(blank=True)
    weights_before          = models.JSONField(default=dict)
    weights_suggested       = models.JSONField(default=dict)

    created_at              = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-audit_date']
        verbose_name = 'Calibration Audit Record'
        verbose_name_plural = 'Calibration Audit Records'


class BuyWaitPrediction(models.Model):
    """
    Records output of buy/wait classifier (offline RL model).
    Logged for every prediction to enable A/B testing and retraining.
    """
    prediction_date         = models.DateTimeField(auto_now_add=True)
    user                    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='buy_wait_predictions',
    )

    # Input features
    property_price_tnd      = models.FloatField()
    delegation              = models.CharField(max_length=100)
    property_type           = models.CharField(max_length=20)
    room_count              = models.IntegerField()
    surface_m2              = models.FloatField()

    # Features used by classifier
    delegation_momentum_3m  = models.FloatField()
    delegation_momentum_12m = models.FloatField()
    opportunity_score       = models.FloatField()
    undervaluation_pct      = models.FloatField()
    estimated_net_yield     = models.FloatField()
    portfolio_concentration_pct = models.FloatField()
    climate_risk_score      = models.FloatField()
    national_interest_rate  = models.FloatField()
    delegation_dom          = models.FloatField()  # days on market

    # Classifier output
    p_good_buy              = models.FloatField()
    predicted_signal        = models.CharField(max_length=20)  # BUY, WAIT, AVOID
    shap_drivers            = models.JSONField(default=dict)  # {feature: contribution}

    # Model version that generated this
    model_version           = models.CharField(max_length=20)
    ab_cohort               = models.CharField(max_length=20, blank=True)  # champion/challenger

    class Meta:
        ordering = ['-prediction_date']
        verbose_name = 'Buy/Wait Prediction'
        verbose_name_plural = 'Buy/Wait Predictions'


class InvestmentScore(models.Model):
    """
    Comprehensive investment analysis for a property.
    Aggregates all 7 scoring models + calibration metadata.
    """
    GRADE_CHOICES = [
        ('A', 'Strong Buy'),
        ('B', 'Buy'),
        ('C', 'Hold'),
        ('D', 'Wait'),
        ('F', 'Avoid'),
    ]

    score_date              = models.DateTimeField(auto_now_add=True)
    user                    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='investment_scores',
    )

    # Property reference
    property_price_tnd      = models.FloatField()
    delegation              = models.CharField(max_length=100)
    property_type           = models.CharField(max_length=20)
    room_count              = models.IntegerField()
    surface_m2              = models.FloatField()

    # Model 1: Undervaluation
    undervaluation_score    = models.FloatField()
    undervaluation_label    = models.CharField(max_length=30, blank=True)

    # Model 2: Yield
    gross_yield_pct         = models.FloatField()
    net_yield_pct           = models.FloatField()
    yield_confidence        = models.CharField(max_length=20)  # high/medium/low

    # Model 3: Buy/Wait (updated by offline RL)
    buy_signal              = models.CharField(max_length=20)  # BUY, WAIT, AVOID
    buy_signal_confidence   = models.FloatField()

    # Model 4: Opportunity Score (composite)
    opportunity_score       = models.FloatField()
    score_breakdown         = models.JSONField(default=dict)
    # {underval: 21.6, yield: 16.3, trend: 20.0, liquidity: 7.0, climate: 5.5}

    # Model 5: Investment Grade
    investment_grade        = models.CharField(max_length=5, choices=GRADE_CHOICES)

    # Model 6: IRR (base case, pessimistic, optimistic)
    irr_base_pct            = models.FloatField()
    irr_pessimistic_pct     = models.FloatField()
    irr_optimistic_pct      = models.FloatField()
    irr_holding_years       = models.IntegerField(default=10)

    # Model 7: Risk (initially simple, upgraded by covariance model)
    risk_score              = models.FloatField()
    risk_label              = models.CharField(max_length=20)  # low/medium/high

    # Alerts and drivers
    key_drivers             = models.JSONField(default=list)
    alerts                  = models.JSONField(default=list)
    shap_explanations       = models.JSONField(default=dict)

    # Versioning
    models_version          = models.JSONField(default=dict)  # {scorer_name: version}

    full_analysis           = models.JSONField(default=dict)

    class Meta:
        ordering = ['-score_date']
        verbose_name = 'Investment Score'
        verbose_name_plural = 'Investment Scores'


class PortfolioAnalysis(models.Model):
    """
    Comprehensive portfolio risk and return analysis.
    Includes covariance-based volatility and diversification metrics.
    """
    analysis_date           = models.DateTimeField(auto_now_add=True)
    user                    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='portfolio_analyses',
    )

    # Portfolio composition
    total_value_tnd         = models.FloatField()
    asset_count             = models.IntegerField()
    delegation_count        = models.IntegerField()

    # Returns
    blended_gross_yield_pct = models.FloatField()
    blended_net_yield_pct   = models.FloatField()
    blended_irr_pct         = models.FloatField()
    irr_pessimistic_pct     = models.FloatField()
    irr_optimistic_pct      = models.FloatField()

    # Risk (covariance-based)
    portfolio_volatility_pct = models.FloatField()
    diversification_ratio   = models.FloatField()  # >1 = benefit
    concentration_pct       = models.FloatField()  # % in top delegation

    # Risk dimensions
    climate_risk_score      = models.FloatField()
    climate_risk_label      = models.CharField(max_length=20)

    # Alerts
    concentration_alerts    = models.JSONField(default=list)
    correlation_alerts      = models.JSONField(default=list)
    diversification_suggestions = models.JSONField(default=list)
    climate_alerts          = models.JSONField(default=list)

    # Covariance matrix (for detailed analysis)
    covariance_matrix       = models.JSONField(default=dict)
    correlation_matrix      = models.JSONField(default=dict)

    full_analysis           = models.JSONField(default=dict)

    class Meta:
        ordering = ['-analysis_date']
        verbose_name = 'Portfolio Analysis'
        verbose_name_plural = 'Portfolio Analyses'
