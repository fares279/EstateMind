"""
ScrapeOrchestrator — ties together scrapers, wrangler, deduplicator, and loader
into a single end-to-end pipeline run for one ScrapeJob.

Thread-safe: each execute_job() call runs inside its own thread.
The caller creates the ScrapeJob record; execute_job() drives it to
completion or failure.
"""

import logging
import threading
import traceback
from datetime import datetime, timezone

from django.db import connection

logger = logging.getLogger(__name__)

_ACTIVE_JOBS: dict[int, threading.Thread] = {}
_LOCK = threading.Lock()


class ScrapeOrchestrator:

    def __init__(self):
        from scraper.models import ScrapeJob, ScrapeSource, ScrapedListing
        from scraper.scrapers import get_scraper_class
        from scraper.pipeline.wrangler import DataWrangler
        from scraper.pipeline.deduplicator import Deduplicator
        from scraper.pipeline.loader import PropertyLoader

        self._ScrapeJob = ScrapeJob
        self._ScrapedListing = ScrapedListing
        self._get_scraper_class = get_scraper_class
        self._wrangler = DataWrangler()
        self._deduplicator = Deduplicator()
        self._loader = PropertyLoader()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def trigger_job(self, source_id: int, triggered_by: str = 'api') -> 'ScrapeJob':
        """
        Create a ScrapeJob and launch it in a background thread.
        Returns the pending job immediately.
        """
        from scraper.models import ScrapeSource, ScrapeJob
        source = ScrapeSource.objects.get(pk=source_id)
        job = ScrapeJob.objects.create(source=source, triggered_by=triggered_by)
        t = threading.Thread(
            target=_run_in_thread,
            args=(job.id,),
            daemon=True,
            name=f"scraper-job-{job.id}",
        )
        with _LOCK:
            _ACTIVE_JOBS[job.id] = t
        t.start()
        logger.info("Launched scrape job #%d for source '%s'", job.id, source.name)
        return job

    def execute_job(self, job_id: int) -> None:
        """
        Full pipeline for one job (runs synchronously — called from thread).
        1. Build scraper from source.scraper_class
        2. scrape_all() → Bronze records
        3. Persist Bronze ScrapedListings
        4. Wrangle Bronze → Silver
        5. Deduplicate
        6. Load Silver → Gold (Property)
        7. Update job counters and mark completed/failed
        """
        from scraper.models import ScrapeJob, ScrapeSource, ScrapedListing
        job = ScrapeJob.objects.select_related('source').get(pk=job_id)
        source = job.source

        job.status = 'running'
        job.started_at = datetime.now(tz=timezone.utc)
        job.save(update_fields=['status', 'started_at'])

        error_lines: list[str] = []

        try:
            # 1 — Build scraper
            ScraperClass = self._get_scraper_class(source.scraper_class)
            scraper = ScraperClass(max_listings=source.max_listings)

            # 2 — Scrape
            raw_records = scraper.scrape_all()
            job.urls_discovered = len(raw_records)
            job.records_scraped = len(raw_records)
            job.save(update_fields=['urls_discovered', 'records_scraped'])

            # 3 — Persist Bronze & process Silver + Gold
            imported = duplicates = normalized = failed = 0

            for raw in raw_records:
                listing_url = str(raw.get('listing_url') or raw.get('source_url') or '')
                title = str(raw.get('title') or '')

                # Compute external_id
                from scraper.scrapers.base import build_external_id
                ext_id = build_external_id(source.name, listing_url, title)

                # 3a — create or skip Bronze record
                listing, created_bronze = ScrapedListing.objects.get_or_create(
                    external_id=ext_id,
                    defaults={
                        'job': job,
                        'source': source,
                        'source_url': listing_url,
                        'status': 'raw',
                        'raw_data': raw,
                    },
                )
                if not created_bronze:
                    # Already in Bronze with this exact id → skip entirely
                    duplicates += 1
                    continue

                # 4 — Wrangle Bronze → Silver
                silver = self._wrangler.wrangle(raw)
                if silver is None:
                    listing.status = 'failed'
                    listing.error_message = 'Wrangler returned None (no title + no price)'
                    listing.save(update_fields=['status', 'error_message'])
                    failed += 1
                    continue

                listing.normalized_data = silver
                listing.normalized_at = datetime.now(tz=timezone.utc)
                listing.status = 'normalized'
                listing.save(update_fields=['normalized_data', 'normalized_at', 'status'])
                normalized += 1

                # 5 — Deduplication against existing Silver records (by URL + fuzzy)
                dup = self._deduplicator.find_duplicate(ext_id, listing_url, silver)
                if dup and dup.pk != listing.pk:
                    listing.status = 'duplicate'
                    listing.duplicate_of = dup
                    listing.save(update_fields=['status', 'duplicate_of'])
                    duplicates += 1
                    continue

                # 6 — Load Silver → Gold
                try:
                    prop, _created = self._loader.load(listing)
                    listing.property = prop
                    listing.imported_at = datetime.now(tz=timezone.utc)
                    listing.status = 'imported'
                    listing.save(update_fields=['property', 'imported_at', 'status'])
                    imported += 1
                except Exception as exc:
                    listing.status = 'failed'
                    listing.error_message = str(exc)[:500]
                    listing.save(update_fields=['status', 'error_message'])
                    error_lines.append(f"{listing_url}: {exc}")
                    failed += 1

            # 7 — Finalise job
            source.last_scraped_at = datetime.now(tz=timezone.utc)
            source.save(update_fields=['last_scraped_at'])

            job.records_normalized = normalized
            job.records_imported = imported
            job.records_duplicates = duplicates
            job.records_failed = failed
            job.status = 'completed'
            job.finished_at = datetime.now(tz=timezone.utc)
            job.error_log = '\n'.join(error_lines)
            job.save()

            logger.info(
                "Job #%d completed — scraped=%d normalized=%d imported=%d "
                "duplicates=%d failed=%d",
                job_id, job.records_scraped, normalized, imported, duplicates, failed,
            )

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Job #%d FAILED: %s\n%s", job_id, exc, tb)
            job.status = 'failed'
            job.finished_at = datetime.now(tz=timezone.utc)
            job.error_log = tb[:5000]
            job.save(update_fields=['status', 'finished_at', 'error_log'])
        finally:
            with _LOCK:
                _ACTIVE_JOBS.pop(job_id, None)


def _run_in_thread(job_id: int) -> None:
    """Thread entry point — ensures DB connections are closed on thread exit."""
    try:
        orchestrator = ScrapeOrchestrator()
        orchestrator.execute_job(job_id)
    finally:
        connection.close()
