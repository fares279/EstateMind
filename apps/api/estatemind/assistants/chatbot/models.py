"""
Chatbot models for Module 9.
Session tracking, response logging, and reward model versioning.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone


class ChatbotSession(models.Model):
    """
    Tracks conversation sessions with context and metadata.
    """
    
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_active_at = models.DateTimeField(auto_now=True)
    turn_count = models.IntegerField(default=0)
    
    # Extracted facts that persist across conversation
    primary_location_interest = models.CharField(
        max_length=100, null=True, blank=True
    )
    preferred_property_type = models.CharField(
        max_length=50, null=True, blank=True,
        choices=[
            ('apartment', 'Apartment'),
            ('house', 'House'),
            ('villa', 'Villa'),  # older sessions; new ones store 'house'
            ('land', 'Land'),
            ('commercial', 'Commercial')
        ]
    )
    investment_horizon = models.CharField(
        max_length=20, null=True, blank=True,
        choices=[
            ('current', 'Current'),
            ('12_months', '12 Months'),
            ('long_term', 'Long Term')
        ]
    )
    
    # Serialized memory (JSON) for Redis backup
    memory_snapshot = models.JSONField(
        default=dict,
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'chatbot_session'
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['started_at']),
            models.Index(fields=['last_active_at']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f'Session {self.session_id[:8]}... ({self.turn_count} turns)'


class ChatbotResponseLog(models.Model):
    """
    Logs every response for quality monitoring and RLHF training.
    """
    
    QUALITY_CHOICES = [
        ('GOOD', 'Good'),
        ('ACCEPTABLE', 'Acceptable'),
        ('POOR', 'Poor'),
    ]
    
    FEEDBACK_CHOICES = [
        ('thumbs_up', 'Thumbs Up'),
        ('thumbs_down', 'Thumbs Down'),
    ]
    
    session = models.ForeignKey(
        ChatbotSession,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    turn_index = models.IntegerField()
    intent = models.CharField(max_length=50, db_index=True)
    query = models.TextField()
    response = models.TextField()
    
    # Quality dimensions
    relevance_score = models.FloatField(null=True, blank=True)
    groundedness_score = models.FloatField(null=True, blank=True)
    length_appropriate = models.BooleanField(null=True, blank=True)
    has_source_attribution = models.BooleanField(null=True, blank=True)
    overall_quality_score = models.FloatField(
        null=True, blank=True, db_index=True
    )
    quality_label = models.CharField(
        max_length=20, null=True, blank=True,
        choices=QUALITY_CHOICES
    )
    
    # Grounding details
    ungrounded_claims = models.JSONField(default=list, blank=True)
    retrieval_sources_used = models.JSONField(default=list, blank=True)
    is_grounded = models.BooleanField(null=True, blank=True)
    
    # User feedback
    user_feedback = models.CharField(
        max_length=20, null=True, blank=True,
        choices=FEEDBACK_CHOICES,
        db_index=True
    )
    feedback_text = models.TextField(
        null=True, blank=True,
        help_text='Optional user feedback text accompanying thumbs_up/down'
    )
    feedback_at = models.DateTimeField(null=True, blank=True)
    
    # Intent classification metadata
    intent_confidence = models.FloatField(
        null=True, blank=True,
        help_text='Confidence score of intent classification'
    )
    secondary_intent = models.CharField(
        max_length=50, null=True, blank=True,
        help_text='Secondary intent if classification was ambiguous'
    )
    extraction_metadata = models.JSONField(
        default=dict, blank=True,
        help_text='Extracted entities (location, property_type, timeframe)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'chatbot_response_log'
        indexes = [
            models.Index(fields=['session', 'turn_index']),
            models.Index(fields=['overall_quality_score']),
            models.Index(fields=['user_feedback']),
            models.Index(fields=['created_at']),
            models.Index(fields=['intent', 'quality_label']),
        ]
    
    def __str__(self):
        return f'Turn {self.turn_index} ({self.quality_label})'
    
    def add_feedback(self, feedback: str, feedback_text: str = None):
        """Records user feedback and timestamps it."""
        self.user_feedback = feedback
        self.feedback_text = feedback_text
        self.feedback_at = timezone.now()
        self.save()


class RewardModelVersion(models.Model):
    """
    Tracks reward model versions and training metadata.
    """
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('retired', 'Retired'),
        ('failed', 'Failed'),
    ]
    
    version = models.CharField(
        max_length=50, unique=True, db_index=True
    )
    trained_at = models.DateTimeField(auto_now_add=True, db_index=True)
    training_examples = models.IntegerField()
    thumbs_up_count = models.IntegerField()
    thumbs_down_count = models.IntegerField()
    cross_val_auc = models.FloatField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active'
    )
    artifact_path = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'reward_model_version'
        ordering = ['-trained_at']
    
    def __str__(self):
        return f'Model {self.version} (AUC {self.cross_val_auc:.3f})'
    
    def deactivate(self):
        """Marks model as retired."""
        self.status = 'retired'
        self.save()


class IntentAccuracyMetric(models.Model):
    """
    Tracks intent classifier accuracy over time.
    Evaluated weekly by Celery task.
    """
    
    evaluated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Accuracy metrics
    total_queries_tested = models.IntegerField()
    correct_predictions = models.IntegerField()
    accuracy = models.FloatField()
    
    # Per-intent breakdown
    accuracy_by_intent = models.JSONField(default=dict)
    confusion_matrix = models.JSONField(default=dict)
    
    # Test set size
    test_set_size = models.IntegerField()
    
    class Meta:
        db_table = 'intent_accuracy_metric'
        ordering = ['-evaluated_at']
    
    def __str__(self):
        return f'Intent Accuracy {self.evaluated_at.date()}: {self.accuracy:.1%}'


class ResponseQualityDailyReport(models.Model):
    """
    Daily aggregation of response quality statistics.
    Used for monitoring and alerting on quality degradation.
    """
    
    report_date = models.DateField(db_index=True, unique=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    
    # Aggregate statistics
    total_responses = models.IntegerField()
    good_responses = models.IntegerField()
    acceptable_responses = models.IntegerField()
    poor_responses = models.IntegerField()
    
    avg_relevance_score = models.FloatField()
    avg_groundedness_score = models.FloatField()
    avg_overall_score = models.FloatField()
    
    # Grounding statistics
    fully_grounded_count = models.IntegerField()
    grounding_rate = models.FloatField()
    
    # User feedback statistics
    total_feedback_received = models.IntegerField()
    thumbs_up_count = models.IntegerField()
    thumbs_down_count = models.IntegerField()
    feedback_rate = models.FloatField()  # % of responses with feedback
    
    # Top intents
    top_intents = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'response_quality_daily_report'
        ordering = ['-report_date']
    
    def __str__(self):
        return f'Quality Report {self.report_date}: {self.avg_overall_score:.2f} avg'
