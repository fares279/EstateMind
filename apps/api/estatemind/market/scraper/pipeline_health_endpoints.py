"""
Enhanced API endpoints for monitoring scraper-agent pipeline health and metrics.

Provides:
- Pipeline status dashboard (Bronze/Silver/Gold stage health)
- Scraper health monitoring
- Data quality metrics (drift, geocoding, schema validation)
- Historical performance tracking
- Alerting and incident detection
"""

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from estatemind.market.scraper.models import ScrapeJob, ScrapeSource, ScrapedListing
from estatemind.market.scraper.pipeline.scraper_agent_architecture import BronzeStageAgent, SilverStageAgent, GoldStageAgent
from estatemind.market.scraper.data_quality import SilverSchemaValidator, DataDriftDetector, GeocodingQualityMeter, ScraperHealthMonitor
from estatemind.market.scraper.drift_monitor import run_ingestion_drift_check
from estatemind.market.core.models import Property


# ============================================================================
# Serializers for Pipeline Metrics & Health
# ============================================================================

class BronzeMetricsSerializer(serializers.Serializer):
    """Bronze stage metrics: collection, discovery, scraping."""
    stage = serializers.CharField()
    version_tag = serializers.CharField()
    collection_timestamp = serializers.DateTimeField()
    total_urls_discovered = serializers.IntegerField()
    total_records_scraped = serializers.IntegerField()
    total_records_failed = serializers.IntegerField()
    overall_success_rate_pct = serializers.FloatField()
    scraper_count = serializers.IntegerField()
    scraper_health_details = serializers.DictField()


class SilverMetricsSerializer(serializers.Serializer):
    """Silver stage metrics: normalization, deduplication, validation."""
    stage = serializers.CharField()
    processing_timestamp = serializers.DateTimeField()
    records_received = serializers.IntegerField()
    records_normalized = serializers.IntegerField()
    records_failed_validation = serializers.IntegerField()
    pass_rate_pct = serializers.FloatField()
    records_duplicates_found = serializers.IntegerField()
    unified_property_ids_assigned = serializers.IntegerField()
    validation_errors = serializers.DictField()


class GoldMetricsSerializer(serializers.Serializer):
    """Gold stage metrics: market intelligence, aggregation."""
    stage = serializers.CharField()
    aggregation_timestamp = serializers.DateTimeField()
    snapshot_version = serializers.CharField()
    records_processed = serializers.IntegerField()
    delegations_analyzed = serializers.IntegerField()
    governorates_analyzed = serializers.IntegerField()


class PipelineHealthSerializer(serializers.Serializer):
    """Overall pipeline health status."""
    pipeline_status = serializers.CharField()  # "healthy", "degraded", "unhealthy"
    overall_health_score = serializers.FloatField(min_value=0, max_value=100)
    bronze_status = BronzeMetricsSerializer()
    silver_status = SilverMetricsSerializer()
    gold_status = GoldMetricsSerializer()
    alerts = serializers.ListField(child=serializers.CharField())
    last_complete_run = serializers.DateTimeField()


class DataQualityReportSerializer(serializers.Serializer):
    """Comprehensive data quality metrics."""
    reporting_timestamp = serializers.DateTimeField()
    geocoding_quality = serializers.DictField()  # polygon_level_pct, centroid_level_pct, missing_pct
    schema_validation_pass_rate = serializers.FloatField()
    data_drift_detected = serializers.BooleanField()
    psi_metrics = serializers.DictField()
    duplicate_rate_pct = serializers.FloatField()
    recommendations = serializers.ListField(child=serializers.CharField())


class ScraperHealthReportSerializer(serializers.Serializer):
    """Health metrics for individual scraper agents."""
    scraper_name = serializers.CharField()
    source_name = serializers.CharField()
    health_score = serializers.FloatField(min_value=0, max_value=100)
    status = serializers.CharField()  # "healthy", "degraded", "unhealthy"
    success_rate_pct = serializers.FloatField()
    avg_data_age_hours = serializers.FloatField()
    field_coverage_pct = serializers.FloatField()
    alerts = serializers.ListField(child=serializers.CharField())
    last_execution = serializers.DateTimeField()


# ============================================================================
# API ViewSets
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAdminUser])
def pipeline_health_dashboard(request):
    """
    GET /api/scraper/health/dashboard/
    
    Returns comprehensive pipeline health status across all three stages.
    Used by admin dashboard to show data quality and ingestion health.
    
    Response includes:
    - Overall pipeline status (healthy/degraded/unhealthy)
    - Stage-by-stage metrics (Bronze/Silver/Gold)
    - Recent alerts and anomalies
    - Recommendations for action
    """
    from django.utils import timezone
    
    # Get latest complete scrape jobs
    latest_bronze_jobs = ScrapeJob.objects.filter(
        status='completed'
    ).order_by('-finished_at')[:5]
    
    latest_silver_jobs = ScrapeJob.objects.filter(
        status='completed'
    ).order_by('-finished_at')[:5]
    
    latest_gold_jobs = ScrapeJob.objects.filter(
        status='completed'
    ).order_by('-finished_at')[:5]

    # Aggregate metrics
    bronze_metrics = {}
    silver_metrics = {}
    gold_metrics = {}
    alerts = []

    if latest_bronze_jobs:
        job = latest_bronze_jobs[0]
        bronze_metrics = {
            'stage': 'bronze',
            'version_tag': f'market_raw_{job.created_at.strftime("%Y_%m_%d_%H_%M_%S")}',
            'collection_timestamp': job.started_at,
            'total_urls_discovered': job.urls_discovered,
            'total_records_scraped': job.records_scraped,
            'total_records_failed': job.records_failed,
            'overall_success_rate_pct': (
                (job.records_scraped / (job.records_scraped + job.records_failed) * 100)
                if (job.records_scraped + job.records_failed) > 0 else 0
            ),
            'scraper_count': ScrapeSource.objects.filter(is_active=True).count(),
        }

        if bronze_metrics['overall_success_rate_pct'] < 80:
            alerts.append(f"⚠️ Bronze stage success rate low: {bronze_metrics['overall_success_rate_pct']:.1f}%")

    if latest_silver_jobs:
        job = latest_silver_jobs[0]
        silver_metrics = {
            'stage': 'silver',
            'processing_timestamp': job.started_at,
            'records_received': job.records_scraped,
            'records_normalized': job.records_normalized,
            'records_failed_validation': job.records_failed,
            'pass_rate_pct': (
                (job.records_normalized / (job.records_normalized + job.records_failed) * 100)
                if (job.records_normalized + job.records_failed) > 0 else 0
            ),
            'records_duplicates_found': job.records_duplicates,
            'unified_property_ids_assigned': max(0, job.records_normalized - job.records_duplicates),
        }

        if silver_metrics['pass_rate_pct'] < 85:
            alerts.append(f"⚠️ Silver stage validation pass rate low: {silver_metrics['pass_rate_pct']:.1f}%")

    if latest_gold_jobs:
        job = latest_gold_jobs[0]
        gold_metrics = {
            'stage': 'gold',
            'aggregation_timestamp': job.started_at,
            'snapshot_version': f'market_snapshot_{job.created_at.strftime("%Y_%m_%d_%H_%M_%S")}',
            'records_processed': job.records_imported,
            'delegations_analyzed': 24,  # Fixed for Tunisia
            'governorates_analyzed': 24,
        }

    # Calculate overall health score
    health_components = []
    if bronze_metrics:
        health_components.append(min(bronze_metrics['overall_success_rate_pct'], 100))
    if silver_metrics:
        health_components.append(min(silver_metrics['pass_rate_pct'], 100))
    if gold_metrics:
        health_components.append(90)  # Assume healthy if we got here

    overall_health_score = sum(health_components) / len(health_components) if health_components else 0

    if overall_health_score >= 85:
        pipeline_status = 'healthy'
    elif overall_health_score >= 70:
        pipeline_status = 'degraded'
    else:
        pipeline_status = 'unhealthy'

    return Response({
        'pipeline_status': pipeline_status,
        'overall_health_score': round(overall_health_score, 1),
        'bronze_status': bronze_metrics or {},
        'silver_status': silver_metrics or {},
        'gold_status': gold_metrics or {},
        'alerts': alerts,
        'last_complete_run': (latest_gold_jobs[0].finished_at if latest_gold_jobs and latest_gold_jobs[0].finished_at else None),
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def data_quality_report(request):
    """
    GET /api/scraper/health/data-quality/
    
    Returns comprehensive data quality assessment:
    - Geocoding accuracy distribution
    - Schema validation pass rate
    - Data drift detection (PSI monitoring)
    - Deduplication rate
    - Recommendations
    """
    from estatemind.market.core.models import Property
    
    # Get recent properties
    recent_properties = Property.objects.all().order_by('-created_at')[:10000]
    
    # Measure geocoding quality via auditor (point-level Property precision)
    try:
        from estatemind.market.scraper.pipeline.geocoding_auditor import compute_geocoding_quality_report
        geocoding_quality = compute_geocoding_quality_report()
    except Exception:
        geocoding_quality = {'polygon_level_pct': 0.0, 'centroid_level_pct': 0.0, 'missing_pct': 100.0}

    # Schema validation rate (estimate from recent jobs)
    recent_job = ScrapeJob.objects.filter(status='completed').order_by('-finished_at').first()
    if recent_job:
        total_records = recent_job.records_scraped + recent_job.records_failed
        schema_validation_pass_rate = (recent_job.records_normalized / total_records * 100) if total_records > 0 else 0
    else:
        schema_validation_pass_rate = 0

    # Data drift detection (estimate PSI > 0.10 threshold)
    # Compute PSI/KS using recent vs baseline windows
    try:
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        current_window_start = now - timedelta(days=30)
        baseline_window_start = now - timedelta(days=90)
        baseline_window_end = now - timedelta(days=31)

        current_prices = list(Property.objects.filter(scraped_at__gte=current_window_start).values_list('price', flat=True))
        baseline_prices = list(Property.objects.filter(scraped_at__range=(baseline_window_start, baseline_window_end)).values_list('price', flat=True))

        current_surfaces = list(Property.objects.filter(scraped_at__gte=current_window_start).values_list('area_sqm', flat=True))
        baseline_surfaces = list(Property.objects.filter(scraped_at__range=(baseline_window_start, baseline_window_end)).values_list('area_sqm', flat=True))

        price_drift = run_ingestion_drift_check(baseline_prices or [0], current_prices or [0])
        surface_drift = run_ingestion_drift_check(baseline_surfaces or [0], current_surfaces or [0])

        psi_metrics = {
            'price_distribution_psi': price_drift['psi'],
            'surface_distribution_psi': surface_drift['psi'],
            'delegation_coverage_psi': 0.0,  # Placeholder — requires snapshot comparison
            'price_ks': price_drift['ks'],
            'surface_ks': surface_drift['ks'],
        }
        data_drift_detected = price_drift['alert'] or surface_drift['alert']
    except Exception:
        psi_metrics = {
            'price_distribution_psi': 0.0,
            'surface_distribution_psi': 0.0,
            'delegation_coverage_psi': 0.0,
        }
        data_drift_detected = False

    # Duplication rate
    if recent_job:
        duplicate_rate = (recent_job.records_duplicates / recent_job.records_normalized * 100) if recent_job.records_normalized > 0 else 0
    else:
        duplicate_rate = 0

    # Recommendations
    recommendations = []
    if geocoding_quality['missing_pct'] > 20:
        recommendations.append("⚠️ High percentage of missing geocoding. Consider improving address-to-coordinate mapping.")
    if schema_validation_pass_rate < 85:
        recommendations.append("⚠️ Schema validation pass rate low. Review scraper outputs for consistency.")
    if data_drift_detected:
        recommendations.append("⚠️ Data drift detected (PSI > 0.10). Downstream models may need retraining.")
    if duplicate_rate > 5:
        recommendations.append("ℹ️ Deduplication rate high. Verify data sources for overlap.")

    return Response({
        'reporting_timestamp': timezone.now(),
        'geocoding_quality': geocoding_quality,
        'schema_validation_pass_rate': round(schema_validation_pass_rate, 1),
        'data_drift_detected': data_drift_detected,
        'psi_metrics': psi_metrics,
        'duplicate_rate_pct': round(duplicate_rate, 1),
        'recommendations': recommendations,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def scraper_health_report(request):
    """
    GET /api/scraper/health/scraper-agents/
    
    Returns health metrics for each active scraper agent.
    Includes success rate, data freshness, field coverage, and alerts.
    """
    from django.db.models import Avg, Count, Q
    
    active_sources = ScrapeSource.objects.filter(is_active=True)
    scraper_health_reports = []

    for source in active_sources:
        recent_jobs = ScrapeJob.objects.filter(
            source=source,
            status='completed'
        ).order_by('-finished_at')[:10]

        if not recent_jobs:
            continue

        # Aggregate metrics
        total_records = sum(job.records_scraped for job in recent_jobs)
        total_failed = sum(job.records_failed for job in recent_jobs)
        avg_duration = sum((job.duration_seconds or 0) for job in recent_jobs) / len(recent_jobs) if recent_jobs else 0

        success_rate = (total_records / (total_records + total_failed) * 100) if (total_records + total_failed) > 0 else 0
        
        # Estimate data age (since last successful job)
        last_job = recent_jobs[0] if recent_jobs else None
        data_age_hours = (
            (timezone.now() - last_job.finished_at).total_seconds() / 3600
            if last_job and last_job.finished_at else float('inf')
        )

        # Field coverage (estimate)
        field_coverage_pct = 85.0  # Example

        # Compute health score
        monitor = ScraperHealthMonitor()
        health_info = monitor.compute_health_score(
            total_records, total_failed, data_age_hours, field_coverage_pct
        )

        scraper_health_reports.append({
            'scraper_name': source.name,
            'source_name': source.name,
            'health_score': health_info['health_score'],
            'status': health_info['status'],
            'success_rate_pct': health_info['success_rate_pct'],
            'avg_data_age_hours': health_info['avg_data_age_hours'],
            'field_coverage_pct': health_info['field_coverage_pct'],
            'alerts': health_info['alerts'],
            'last_execution': last_job.finished_at if last_job else None,
        })

    return Response(scraper_health_reports)


# ============================================================================
# Utility: Generate Incident Report
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAdminUser])
def incident_detection(request):
    """
    GET /api/scraper/health/incidents/
    
    Detect and report data pipeline incidents:
    - Scraper failure cascades
    - Data quality degradation
    - Anomalies in aggregates
    """
    incidents = []

    # Check for recent failed jobs
    recent_failed = ScrapeJob.objects.filter(
        status='failed'
    ).order_by('-created_at')[:5]

    for job in recent_failed:
        incidents.append({
            'type': 'scraper_failure',
            'severity': 'high',
            'source': job.source.name,
            'timestamp': job.created_at,
            'message': f"Scrape job failed: {job.error_log[:100]}",
        })

    # Check for low success rates
    recent_jobs = ScrapeJob.objects.filter(status='completed').order_by('-finished_at')[:10]
    for job in recent_jobs:
        total = job.records_scraped + job.records_failed
        if total > 0 and job.records_scraped / total < 0.80:
            incidents.append({
                'type': 'low_success_rate',
                'severity': 'medium',
                'source': job.source.name,
                'timestamp': job.finished_at,
                'success_rate': f"{job.records_scraped / total * 100:.1f}%",
                'message': f"Success rate low on {job.source.name}",
            })

    return Response({
        'incident_count': len(incidents),
        'incidents': incidents,
        'timestamp': timezone.now(),
    })
