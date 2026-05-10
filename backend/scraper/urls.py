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
)

router = DefaultRouter()
router.register(r'sources', ScrapeSourceViewSet, basename='scraper-sources')
router.register(r'jobs', ScrapeJobViewSet, basename='scraper-jobs')
router.register(r'listings', ScrapedListingViewSet, basename='scraper-listings')

urlpatterns = [
    path('', include(router.urls)),
    path('jobs/trigger/', trigger_scrape_job, name='scraper-trigger-job'),
    path('jobs/trigger-all/', trigger_all_sources, name='scraper-trigger-all'),
    path('pipeline/run/', run_pipeline, name='scraper-pipeline-run'),
    path('stats/', scraper_stats, name='scraper-stats'),
]
