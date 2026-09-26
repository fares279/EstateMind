import logging
import csv
from io import StringIO
from datetime import datetime, timezone

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .data_quality import SilverSchemaValidator
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
    from .models import ScrapeJob, ScrapeSource

    source = ScrapeSource.objects.get(pk=source_id)
    # Create job record (queued)
    job = ScrapeJob.objects.create(source=source, triggered_by='api', status='pending')

    # Try to enqueue Celery task, fallback to threaded orchestrator
    try:
        from .tasks import run_scraper_pipeline
        run_scraper_pipeline.delay(job.id)
    except Exception:
        # Celery not configured or import failed — fallback to existing threaded runner
        from .services.orchestrator import ScrapeOrchestrator
        orchestrator = ScrapeOrchestrator()
        orchestrator.trigger_job(source_id=source_id, triggered_by='api')

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

    from .models import ScrapeJob

    jobs = []
    # Create job records first
    for s in sources:
        job = ScrapeJob.objects.create(source=s, triggered_by='api_all', status='pending')
        jobs.append(job)

    # Try to enqueue tasks in bulk; if Celery unavailable, fallback to orchestrator triggers
    try:
        from .tasks import run_scraper_pipeline
        for job in jobs:
            run_scraper_pipeline.delay(job.id)
    except Exception:
        from .services.orchestrator import ScrapeOrchestrator
        orchestrator = ScrapeOrchestrator()
        for s in sources:
            orchestrator.trigger_job(source_id=s.pk, triggered_by='api_all')

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


def _quality_review_metadata(listing):
    normalized_data = listing.normalized_data or {}
    review = normalized_data.get('_quality_review')
    return review if isinstance(review, dict) else {}


def _build_suggestions(field_name, current_value):
    if field_name == 'price_tnd':
        return ['100000', '250000', '500000']
    if field_name == 'surface_m2':
        return ['50', '80', '120']
    if field_name == 'governorate':
        return ['Tunis', 'Ariana', 'Sousse']
    if field_name in {'location_lat', 'location_lon'}:
        return [str(current_value or ''), '32.887', '10.179']
    return [str(current_value or '')]


def _derive_violation(listing):
    review = _quality_review_metadata(listing)
    if review:
        return {
            'id': listing.pk,
            'record_id': listing.external_id,
            'violation_type': review.get('violation_type', 'schema_mismatch'),
            'severity': review.get('severity', 'warning'),
            'source': listing.source.name,
            'field_name': review.get('field_name', 'unknown'),
            'message': review.get('message', 'Quality review record'),
            'constraint': review.get('constraint', ''),
            'original_value': review.get('original_value'),
            'status': review.get('status', 'pending'),
            'suggestions': review.get('suggestions', []),
            'created_at': listing.scraped_at,
            'reviewed_at': review.get('reviewed_at'),
        }

    candidate_data = listing.normalized_data or listing.raw_data or {}
    validator = SilverSchemaValidator()
    is_valid, errors = validator.validate_record(candidate_data if isinstance(candidate_data, dict) else {})

    if is_valid:
        return None

    first_error = errors[0] if errors else 'Record failed validation'
    field_name = 'unknown'
    for known_field in SilverSchemaValidator.SCHEMA.keys():
        if known_field in first_error:
            field_name = known_field
            break

    severity = 'critical' if listing.status == 'failed' else 'warning'
    violation_type = 'validation_failed' if listing.status == 'failed' else 'schema_mismatch'

    return {
        'id': listing.pk,
        'record_id': listing.external_id,
        'violation_type': violation_type,
        'severity': severity,
        'source': listing.source.name,
        'field_name': field_name,
        'message': first_error,
        'constraint': first_error,
        'original_value': candidate_data.get(field_name) if isinstance(candidate_data, dict) else None,
        'status': 'pending',
        'suggestions': _build_suggestions(field_name, candidate_data.get(field_name) if isinstance(candidate_data, dict) else None),
        'created_at': listing.scraped_at,
        'reviewed_at': None,
    }


def _collect_violations(status_filter=None, severity_filter=None, source_filter=None):
    queryset = ScrapedListing.objects.select_related('source').order_by('-scraped_at')[:500]
    violations = []

    for listing in queryset:
        violation = _derive_violation(listing)
        if not violation:
            continue

        if status_filter and status_filter != 'all' and violation['status'] != status_filter:
            continue
        if severity_filter and severity_filter != 'all' and violation['severity'] != severity_filter:
            continue
        if source_filter and source_filter != 'all':
            source_value = str(source_filter).lower()
            if source_value not in listing.source.name.lower():
                continue

        violations.append(violation)

    return violations


@api_view(['GET'])
@permission_classes([IsAdminUser])
def data_quality_violations(request):
    """Return current and historical scraper data quality violations."""
    status_filter = request.query_params.get('status', 'all')
    severity_filter = request.query_params.get('severity', 'all')
    source_filter = request.query_params.get('source', 'all')

    violations = _collect_violations(status_filter, severity_filter, source_filter)
    pending_count = sum(1 for item in violations if item['status'] == 'pending')
    approved_count = sum(1 for item in violations if item['status'] == 'approved')
    rejected_count = sum(1 for item in violations if item['status'] == 'rejected')
    fixed_count = sum(1 for item in violations if item['status'] == 'fixed')

    return Response({
        'violations': violations,
        'stats': {
            'total_violations': len(violations),
            'pending_violations': pending_count,
            'approved_violations': approved_count + fixed_count,
            'rejected_violations': rejected_count,
            'fixed_violations': fixed_count,
        },
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def approve_data_quality_violation(request, pk):
    """Record a manual correction for a scraped listing."""
    listing = get_object_or_404(ScrapedListing.objects.select_related('source'), pk=pk)
    corrected_data = request.data.get('corrected_data')
    field_name = request.data.get('field_name')

    normalized_data = dict(listing.normalized_data or {})
    review = dict(normalized_data.get('_quality_review') or {})

    if isinstance(corrected_data, dict):
        normalized_data.update(corrected_data)
        corrected_value = corrected_data.get(field_name) if field_name else corrected_data
    else:
        corrected_value = corrected_data
        if field_name:
            normalized_data[field_name] = corrected_data

    review.update({
        'status': 'fixed',
        'field_name': field_name or review.get('field_name', 'unknown'),
        'corrected_value': corrected_value,
        'reviewed_at': datetime.now(tz=timezone.utc).isoformat(),
        'reviewed_by': request.user.email,
    })
    if 'violation_type' not in review:
        review['violation_type'] = 'schema_mismatch'
    if 'severity' not in review:
        review['severity'] = 'warning'
    if 'message' not in review:
        review['message'] = 'Record corrected by admin review'
    normalized_data['_quality_review'] = review
    listing.normalized_data = normalized_data
    if listing.status in {'raw', 'failed'}:
        listing.status = 'normalized'
    listing.error_message = ''
    listing.save(update_fields=['normalized_data', 'status', 'error_message'])

    return Response(_derive_violation(listing), status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reject_data_quality_violation(request, pk):
    """Mark a listing as rejected during manual quality review."""
    listing = get_object_or_404(ScrapedListing.objects.select_related('source'), pk=pk)
    normalized_data = dict(listing.normalized_data or {})
    review = dict(normalized_data.get('_quality_review') or {})

    review.update({
        'status': 'rejected',
        'field_name': request.data.get('field_name', review.get('field_name', 'unknown')),
        'reviewed_at': datetime.now(tz=timezone.utc).isoformat(),
        'reviewed_by': request.user.email,
        'message': 'Rejected by admin review',
    })
    normalized_data['_quality_review'] = review
    listing.normalized_data = normalized_data
    listing.status = 'failed'
    listing.error_message = 'Rejected by admin'
    listing.save(update_fields=['normalized_data', 'status', 'error_message'])

    return Response(_derive_violation(listing), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_data_quality_violations(request):
    """Export the quality review ledger as CSV."""
    violations = _collect_violations(
        request.query_params.get('status', 'all'),
        request.query_params.get('severity', 'all'),
        request.query_params.get('source', 'all'),
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'id', 'record_id', 'status', 'severity', 'source', 'field_name',
        'violation_type', 'message', 'constraint', 'original_value', 'suggestions',
    ])
    for violation in violations:
        writer.writerow([
            violation['id'],
            violation['record_id'],
            violation['status'],
            violation['severity'],
            violation['source'],
            violation['field_name'],
            violation['violation_type'],
            violation['message'],
            violation['constraint'],
            violation['original_value'],
            ' | '.join(map(str, violation['suggestions'])),
        ])

    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="scraper-quality-violations.csv"'
    return response
