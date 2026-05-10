import logging
from datetime import datetime, timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import ScrapeJob, ScrapeSource, ScrapedListing
from .serializers import (
    PipelineRunSerializer,
    ScrapeJobSerializer,
    ScrapedListingDetailSerializer,
    ScrapedListingSerializer,
    ScrapeSourceSerializer,
    TriggerJobSerializer,
)

logger = logging.getLogger(__name__)


class ScrapeSourceViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve configured scraping sources."""
    queryset = ScrapeSource.objects.all().order_by('name')
    serializer_class = ScrapeSourceSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        """Return only active sources."""
        qs = self.queryset.filter(is_active=True)
        return Response(self.get_serializer(qs, many=True).data)


class ScrapeJobViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve scrape job records."""
    queryset = ScrapeJob.objects.select_related('source').order_by('-created_at')
    serializer_class = ScrapeJobSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['status', 'source']


class ScrapedListingViewSet(viewsets.ReadOnlyModelViewSet):
    """Browse the Bronze/Silver layer of scraped listings."""
    queryset = ScrapedListing.objects.select_related('source').order_by('-scraped_at')
    permission_classes = [IsAdminUser]
    filterset_fields = ['status', 'source']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ScrapedListingDetailSerializer
        return ScrapedListingSerializer


@api_view(['POST'])
@permission_classes([IsAdminUser])
def trigger_scrape_job(request):
    """
    POST /api/scraper/jobs/trigger/
    Body: { "source_id": <int> }

    Launches a scrape job in a background thread and returns the job record
    immediately with status='pending'.
    """
    serializer = TriggerJobSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    source_id = serializer.validated_data['source_id']
    from .services.orchestrator import ScrapeOrchestrator
    orchestrator = ScrapeOrchestrator()
    job = orchestrator.trigger_job(source_id=source_id, triggered_by='api')
    return Response(ScrapeJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def trigger_all_sources(request):
    """
    POST /api/scraper/jobs/trigger-all/

    Launches a background job for every active source.
    Returns list of created job records.
    """
    sources = ScrapeSource.objects.filter(is_active=True)
    if not sources.exists():
        return Response({'detail': 'No active sources configured.'}, status=status.HTTP_404_NOT_FOUND)

    from .services.orchestrator import ScrapeOrchestrator
    orchestrator = ScrapeOrchestrator()
    jobs = [orchestrator.trigger_job(source_id=s.pk, triggered_by='api_all') for s in sources]
    return Response(ScrapeJobSerializer(jobs, many=True).data, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def run_pipeline(request):
    """
    POST /api/scraper/pipeline/run/
    Body: { "status": "raw"|"normalized"|"failed", "limit": 200, "source_name": "" }

    Synchronously processes pending ScrapedListings through remaining
    pipeline stages (wrangler → deduplicator → loader).
    Returns a summary dict.
    """
    serializer = PipelineRunSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    from .pipeline.wrangler import DataWrangler
    from .pipeline.deduplicator import Deduplicator
    from .pipeline.loader import PropertyLoader

    status_filter = serializer.validated_data['status']
    limit = serializer.validated_data['limit']
    source_name = serializer.validated_data.get('source_name', '')

    qs = ScrapedListing.objects.filter(status__in=['raw', 'normalized', 'failed'])
    if status_filter:
        qs = qs.filter(status=status_filter)
    if source_name:
        qs = qs.filter(source__name__iexact=source_name)
    qs = qs.order_by('scraped_at')[:limit]
    listings = list(qs)

    wrangler = DataWrangler()
    deduplicator = Deduplicator()
    loader = PropertyLoader()

    normalized_count = imported_count = dup_count = failed_count = 0

    for listing in listings:
        now = datetime.now(tz=timezone.utc)

        if listing.status in ('raw', 'failed') and listing.raw_data:
            silver = wrangler.wrangle(listing.raw_data)
            if not silver:
                listing.status = 'failed'
                listing.error_message = 'Wrangler returned None'
                listing.save(update_fields=['status', 'error_message'])
                failed_count += 1
                continue
            listing.normalized_data = silver
            listing.normalized_at = now
            listing.status = 'normalized'
            listing.save(update_fields=['normalized_data', 'normalized_at', 'status'])
            normalized_count += 1

        if listing.status == 'normalized':
            silver = listing.normalized_data or {}
            dup = deduplicator.find_duplicate(listing.external_id, listing.source_url, silver)
            if dup and dup.pk != listing.pk:
                listing.status = 'duplicate'
                listing.duplicate_of = dup
                listing.save(update_fields=['status', 'duplicate_of'])
                dup_count += 1
                continue
            try:
                prop, _ = loader.load(listing)
                listing.property = prop
                listing.imported_at = datetime.now(tz=timezone.utc)
                listing.status = 'imported'
                listing.save(update_fields=['property', 'imported_at', 'status'])
                imported_count += 1
            except Exception as exc:
                listing.status = 'failed'
                listing.error_message = str(exc)[:500]
                listing.save(update_fields=['status', 'error_message'])
                failed_count += 1
                logger.warning("Loader error: %s", exc)

    return Response({
        'processed': len(listings),
        'normalized': normalized_count,
        'imported': imported_count,
        'duplicates': dup_count,
        'failed': failed_count,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def scraper_stats(request):
    """
    GET /api/scraper/stats/
    Returns high-level statistics about the scraping layer.
    """
    from django.db.models import Count, Sum

    total_listings = ScrapedListing.objects.count()
    by_status = dict(
        ScrapedListing.objects.values_list('status')
        .annotate(c=Count('id'))
        .values_list('status', 'c')
    )

    by_source = list(
        ScrapedListing.objects.values('source__name')
        .annotate(
            total=Count('id'),
            imported=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status='imported')),
        )
        .order_by('source__name')
    )

    total_jobs = ScrapeJob.objects.count()
    recent_jobs = ScrapeJobSerializer(
        ScrapeJob.objects.order_by('-created_at')[:5], many=True
    ).data

    return Response({
        'total_scraped_listings': total_listings,
        'by_status': by_status,
        'by_source': by_source,
        'total_jobs': total_jobs,
        'recent_jobs': recent_jobs,
    })
