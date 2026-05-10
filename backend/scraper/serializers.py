from rest_framework import serializers
from .models import ScrapeSource, ScrapeJob, ScrapedListing


class ScrapeSourceSerializer(serializers.ModelSerializer):
    total_jobs = serializers.SerializerMethodField()
    total_imported = serializers.SerializerMethodField()

    class Meta:
        model = ScrapeSource
        fields = [
            'id', 'name', 'base_url', 'scraper_class', 'is_active',
            'max_listings', 'schedule_hours', 'last_scraped_at',
            'total_jobs', 'total_imported', 'created_at',
        ]
        read_only_fields = ['id', 'last_scraped_at', 'created_at']

    def get_total_jobs(self, obj):
        return obj.jobs.count()

    def get_total_imported(self, obj):
        return obj.scraped_listings.filter(status='imported').count()


class ScrapeJobSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source.name', read_only=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = ScrapeJob
        fields = [
            'id', 'source', 'source_name', 'status', 'triggered_by',
            'started_at', 'finished_at', 'duration_seconds',
            'urls_discovered', 'records_scraped', 'records_normalized',
            'records_imported', 'records_duplicates', 'records_failed',
            'error_log', 'created_at',
        ]
        read_only_fields = ['__all__']

    def get_duration_seconds(self, obj):
        return obj.duration_seconds


class ScrapedListingSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source.name', read_only=True)
    title = serializers.SerializerMethodField()
    governorate = serializers.SerializerMethodField()
    price_tnd = serializers.SerializerMethodField()
    property_type = serializers.SerializerMethodField()

    class Meta:
        model = ScrapedListing
        fields = [
            'id', 'external_id', 'source_name', 'source_url', 'status',
            'title', 'governorate', 'price_tnd', 'property_type',
            'scraped_at', 'normalized_at', 'imported_at',
        ]
        read_only_fields = ['__all__']

    def get_title(self, obj):
        return (obj.raw_data or {}).get('title', '')

    def get_governorate(self, obj):
        return (obj.normalized_data or {}).get('governorate', '')

    def get_price_tnd(self, obj):
        return (obj.normalized_data or {}).get('price_tnd')

    def get_property_type(self, obj):
        return (obj.normalized_data or {}).get('property_type', '')


class ScrapedListingDetailSerializer(ScrapedListingSerializer):
    """Full detail including raw and normalized data blobs."""
    class Meta(ScrapedListingSerializer.Meta):
        fields = ScrapedListingSerializer.Meta.fields + ['raw_data', 'normalized_data', 'error_message']


class TriggerJobSerializer(serializers.Serializer):
    source_id = serializers.IntegerField()

    def validate_source_id(self, value):
        from scraper.models import ScrapeSource
        if not ScrapeSource.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError("No active source with this ID.")
        return value


class PipelineRunSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['raw', 'normalized', 'failed'],
        default='raw',
    )
    limit = serializers.IntegerField(min_value=1, max_value=5000, default=200)
    source_name = serializers.CharField(required=False, allow_blank=True, default='')
