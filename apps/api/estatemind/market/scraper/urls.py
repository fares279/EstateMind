from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ScrapeSourceViewSet,
    ScrapeJobViewSet,
    ScrapedListingViewSet,
    trigger_scrape_job,
    trigger_all_sources,
    run_pipeline,
    scraper_stats,
    data_quality_violations,
    approve_data_quality_violation,
    reject_data_quality_violation,
    export_data_quality_violations,
)
from .pipeline_health_endpoints import (
    pipeline_health_dashboard,
    data_quality_report,
    scraper_health_report,
    incident_detection,
)

router = DefaultRouter()
router.register(r'sources', ScrapeSourceViewSet, basename='scraper-sources')
router.register(r'jobs', ScrapeJobViewSet, basename='scraper-jobs')
router.register(r'listings', ScrapedListingViewSet, basename='scraper-listings')

urlpatterns = [
    path('', include(router.urls)),
    path('health/dashboard/', pipeline_health_dashboard, name='scraper-health-dashboard'),
    path('health/data-quality/', data_quality_report, name='scraper-data-quality-report'),
    path('health/scraper-agents/', scraper_health_report, name='scraper-health-report'),
    path('health/incidents/', incident_detection, name='scraper-incidents'),
    path('jobs/trigger/', trigger_scrape_job, name='scraper-trigger-job'),
    path('jobs/trigger-all/', trigger_all_sources, name='scraper-trigger-all'),
    path('pipeline/run/', run_pipeline, name='scraper-pipeline-run'),
    path('stats/', scraper_stats, name='scraper-stats'),
    path('data-quality/violations/', data_quality_violations, name='scraper-data-quality-violations'),
    path('data-quality/violations/export/', export_data_quality_violations, name='scraper-data-quality-violations-export'),
    path('data-quality/violations/<int:pk>/approve/', approve_data_quality_violation, name='scraper-data-quality-approve'),
    path('data-quality/violations/<int:pk>/reject/', reject_data_quality_violation, name='scraper-data-quality-reject'),
]
