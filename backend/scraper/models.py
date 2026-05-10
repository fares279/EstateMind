from django.db import models


class ScrapeSource(models.Model):
    """
    Configured scraping source (one row per platform).
    Drives which scrapers are active and at what cadence.
    """
    name = models.CharField(max_length=100, unique=True)
    base_url = models.URLField(max_length=500)
    scraper_class = models.CharField(
        max_length=100,
        help_text='Registry key, e.g. TayaraScraper'
    )
    is_active = models.BooleanField(default=True)
    max_listings = models.IntegerField(default=100)
    schedule_hours = models.IntegerField(
        default=24,
        help_text='Minimum hours between scrape runs for this source'
    )
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ScrapeJob(models.Model):
    """
    One scrape execution run for a single source.
    Tracks lifecycle from pending → running → completed/failed.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    source = models.ForeignKey(
        ScrapeSource, on_delete=models.CASCADE, related_name='jobs'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    triggered_by = models.CharField(
        max_length=100, default='system',
        help_text='Who/what triggered this job: system, api, cron, manual'
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    # Progress counters
    urls_discovered = models.IntegerField(default=0)
    records_scraped = models.IntegerField(default=0)
    records_normalized = models.IntegerField(default=0)
    records_imported = models.IntegerField(default=0)
    records_duplicates = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)

    error_log = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Job #{self.id} — {self.source.name} [{self.status}]"

    @property
    def duration_seconds(self):
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class ScrapedListing(models.Model):
    """
    Bronze-Silver-Gold data lake entry for a single scraped property.

    Bronze  : raw_data       — exactly as returned by the scraper
    Silver  : normalized_data — canonical schema after wrangling
    Gold    : property FK    — linked core.Property record after loading
    """
    STATUS_CHOICES = [
        ('raw', 'Raw'),
        ('normalized', 'Normalized'),
        ('imported', 'Imported'),
        ('duplicate', 'Duplicate'),
        ('failed', 'Failed'),
    ]

    job = models.ForeignKey(
        ScrapeJob, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='scraped_listings'
    )
    source = models.ForeignKey(
        ScrapeSource, on_delete=models.CASCADE, related_name='scraped_listings'
    )
    external_id = models.CharField(
        max_length=64, unique=True,
        help_text='SHA-1 hash of source|url|title — deduplication key'
    )
    source_url = models.URLField(max_length=1000)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='raw')

    # Bronze — raw dict from scraper
    raw_data = models.JSONField(default=dict)
    # Silver — normalized canonical schema
    normalized_data = models.JSONField(null=True, blank=True)
    # Gold — linked to core Property model
    property = models.OneToOneField(
        'core.Property', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='scraped_listing'
    )

    duplicate_of = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='duplicates'
    )
    error_message = models.TextField(blank=True, default='')

    scraped_at = models.DateTimeField(auto_now_add=True)
    normalized_at = models.DateTimeField(null=True, blank=True)
    imported_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-scraped_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['source', 'status']),
            models.Index(fields=['scraped_at']),
        ]

    def __str__(self):
        title = (self.raw_data or {}).get('title', self.source_url)
        return f"[{self.status.upper()}] {title[:80]}"
