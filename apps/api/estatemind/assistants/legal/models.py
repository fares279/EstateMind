from django.conf import settings
from django.db import models
from django.utils import timezone


class EmbeddingCollectionVersion(models.Model):
    """
    Registry of all ChromaDB collection versions.
    Each version corresponds to a specific embedding model.
    Collections are never overwritten — each upgrade creates a new version.
    """
    collection_name = models.CharField(max_length=100, unique=True)
    domain = models.CharField(max_length=50)
    embedding_model = models.CharField(max_length=200)
    embedding_version = models.CharField(max_length=20)
    total_passages = models.IntegerField(default=0)
    indexed_date = models.DateField(default=timezone.now)
    recall_at_5 = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, default='indexing')
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.collection_name} ({self.domain}) [{self.status}]"


# ── Conversation, logging and quality tracking ───────────────────────────────
# Mirrors chatbot.ChatbotSession / ChatbotResponseLog /
# ResponseQualityDailyReport / RewardModelVersion for the legal assistant.

class LegalSession(models.Model):
    """A legal Q&A conversation. Memory lives in the cache; this is the durable copy."""

    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_active_at = models.DateTimeField(auto_now=True)
    turn_count = models.IntegerField(default=0)
    last_domain = models.CharField(max_length=50, blank=True, default='')
    memory_snapshot = models.JSONField(default=dict, null=True, blank=True)

    class Meta:
        db_table = 'legal_session'
        indexes = [models.Index(fields=['last_active_at']), models.Index(fields=['user'])]

    def __str__(self):
        return f'Legal session {self.session_id[:8]}... ({self.turn_count} turns)'


class LegalResponseLog(models.Model):
    """Every legal question and what the assistant did with it."""

    QUALITY_CHOICES = [('GOOD', 'Good'), ('ACCEPTABLE', 'Acceptable'), ('POOR', 'Poor')]
    FEEDBACK_CHOICES = [('thumbs_up', 'Thumbs Up'), ('thumbs_down', 'Thumbs Down')]

    OUTCOME_ANSWERED = 'answered'
    OUTCOME_ANSWERED_FLAGGED = 'answered_flagged'
    OUTCOME_NO_SOURCES = 'refused_no_sources'
    OUTCOME_UNGROUNDED = 'refused_ungrounded'
    OUTCOME_OUT_OF_SCOPE = 'out_of_scope'
    OUTCOME_LLM_UNAVAILABLE = 'llm_unavailable'
    OUTCOME_ERROR = 'error'
    OUTCOME_CHOICES = [
        (OUTCOME_ANSWERED, 'Answered, grounded'),
        (OUTCOME_ANSWERED_FLAGGED, 'Answered, some sentences not verified'),
        (OUTCOME_NO_SOURCES, 'Refused: no relevant legal source'),
        (OUTCOME_UNGROUNDED, 'Refused: answer not supported by sources'),
        (OUTCOME_OUT_OF_SCOPE, 'Not a legal question'),
        (OUTCOME_LLM_UNAVAILABLE, 'Language model unreachable'),
        (OUTCOME_ERROR, 'Internal error'),
    ]

    session = models.ForeignKey(LegalSession, on_delete=models.CASCADE, related_name='responses')
    turn_index = models.IntegerField()
    question = models.TextField()
    answer = models.TextField(blank=True)
    language = models.CharField(max_length=5, blank=True, default='')
    outcome = models.CharField(max_length=30, choices=OUTCOME_CHOICES, db_index=True)

    # Classification
    domain = models.CharField(max_length=50, blank=True, default='', db_index=True)
    domain_confidence = models.FloatField(null=True, blank=True)
    in_scope = models.BooleanField(null=True, blank=True)

    # Retrieval
    collection_used = models.CharField(max_length=100, blank=True, default='')
    embedding_model = models.CharField(max_length=200, blank=True, default='')
    retrieval_top_similarity = models.FloatField(null=True, blank=True)
    retrieval_sources = models.JSONField(default=list, blank=True)

    # Generation
    llm_model = models.CharField(max_length=100, blank=True, default='')
    generation_attempts = models.IntegerField(default=0)
    latency_ms = models.IntegerField(null=True, blank=True)

    # Quality dimensions (same scale as ChatbotResponseLog)
    relevance_score = models.FloatField(null=True, blank=True)
    groundedness_score = models.FloatField(null=True, blank=True)
    citation_score = models.FloatField(null=True, blank=True)
    length_appropriate = models.BooleanField(null=True, blank=True)
    overall_quality_score = models.FloatField(null=True, blank=True, db_index=True)
    quality_label = models.CharField(max_length=20, null=True, blank=True, choices=QUALITY_CHOICES)
    is_grounded = models.BooleanField(null=True, blank=True)
    ungrounded_sentences = models.JSONField(default=list, blank=True)
    reward_score = models.FloatField(null=True, blank=True)

    # User feedback (reward model training data)
    user_feedback = models.CharField(max_length=20, null=True, blank=True, choices=FEEDBACK_CHOICES, db_index=True)
    feedback_text = models.TextField(null=True, blank=True)
    feedback_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'legal_response_log'
        indexes = [
            models.Index(fields=['session', 'turn_index']),
            models.Index(fields=['created_at']),
            models.Index(fields=['outcome', 'quality_label']),
        ]

    def __str__(self):
        return f'Legal turn {self.turn_index} ({self.outcome}, {self.quality_label})'

    def add_feedback(self, feedback: str, feedback_text: str | None = None):
        self.user_feedback = feedback
        self.feedback_text = feedback_text
        self.feedback_at = timezone.now()
        self.save(update_fields=['user_feedback', 'feedback_text', 'feedback_at'])


class LegalResponseQualityDailyReport(models.Model):
    """Daily aggregate of legal answer quality, for monitoring and alerting."""

    report_date = models.DateField(db_index=True, unique=True)
    generated_at = models.DateTimeField(auto_now=True)

    total_responses = models.IntegerField()
    outcome_counts = models.JSONField(default=dict)
    answered_count = models.IntegerField()
    refusal_rate = models.FloatField()

    good_responses = models.IntegerField()
    acceptable_responses = models.IntegerField()
    poor_responses = models.IntegerField()
    avg_relevance_score = models.FloatField()
    avg_groundedness_score = models.FloatField()
    avg_overall_score = models.FloatField()
    grounding_rate = models.FloatField()  # of answered responses

    total_feedback_received = models.IntegerField()
    thumbs_up_count = models.IntegerField()
    thumbs_down_count = models.IntegerField()
    feedback_rate = models.FloatField()

    top_domains = models.JSONField(default=dict)

    class Meta:
        db_table = 'legal_response_quality_daily_report'
        ordering = ['-report_date']

    def __str__(self):
        return f'Legal quality report {self.report_date}: {self.avg_overall_score:.2f} avg'


class LegalRewardModelVersion(models.Model):
    """Reward model versions trained on legal answer feedback."""

    STATUS_CHOICES = [('active', 'Active'), ('retired', 'Retired'), ('failed', 'Failed')]

    version = models.CharField(max_length=50, unique=True, db_index=True)
    trained_at = models.DateTimeField(auto_now_add=True, db_index=True)
    training_examples = models.IntegerField()
    thumbs_up_count = models.IntegerField()
    thumbs_down_count = models.IntegerField()
    cross_val_auc = models.FloatField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    artifact_path = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'legal_reward_model_version'
        ordering = ['-trained_at']

    def __str__(self):
        return f'Legal reward model {self.version} (AUC {self.cross_val_auc:.3f})'
