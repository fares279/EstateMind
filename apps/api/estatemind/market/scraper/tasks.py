from __future__ import annotations

import logging
from celery import shared_task

from estatemind.market.scraper.services.orchestrator import ScrapeOrchestrator
from estatemind.market.scraper.models import ScrapeJob

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, soft_time_limit=60 * 60)
def run_scraper_pipeline(self, job_id: int) -> dict:
    """Celery task wrapper to run the full orchestrator pipeline for a job id."""
    try:
        job = ScrapeJob.objects.select_related('source').get(pk=job_id)
    except ScrapeJob.DoesNotExist:
        logger.error("ScrapeJob %s not found", job_id)
        return {'status': 'missing'}

    try:
        orchestrator = ScrapeOrchestrator()
        orchestrator.execute_job(job_id)
        return {'status': 'completed', 'job_id': job_id}
    except Exception as exc:
        logger.exception("Task run_scraper_pipeline failed for job %s", job_id)
        raise self.retry(exc=exc, countdown=60)
