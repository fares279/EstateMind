"""
Management command: run_scrapers

Triggers one synchronous scrape-and-load pipeline run.
By default runs all active sources sequentially.

Usage examples
--------------
# Run all active sources
python manage.py run_scrapers

# Run a specific source by name
python manage.py run_scrapers --source tayara

# Dry-run: scrape only, do not persist anything
python manage.py run_scrapers --dry-run

# Limit listings per source
python manage.py run_scrapers --max-listings 20
"""

import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Run real-time scrapers and load results into the property database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            default=None,
            help='Source name to run (default: all active sources)',
        )
        parser.add_argument(
            '--max-listings',
            type=int,
            default=None,
            help='Override max_listings for this run',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Scrape only — do not persist Bronze, Silver, or Gold records',
        )

    def handle(self, *args, **options):
        from scraper.models import ScrapeSource, ScrapeJob, ScrapedListing
        from scraper.scrapers import get_scraper_class
        from scraper.pipeline.wrangler import DataWrangler
        from scraper.pipeline.deduplicator import Deduplicator
        from scraper.pipeline.loader import PropertyLoader
        from scraper.scrapers.base import build_external_id
        from datetime import datetime, timezone as tz

        source_filter = options['source']
        max_listings_override = options['max_listings']
        dry_run = options['dry_run']

        qs = ScrapeSource.objects.filter(is_active=True)
        if source_filter:
            qs = qs.filter(name__iexact=source_filter)
            if not qs.exists():
                raise CommandError(f"No active source named '{source_filter}'")

        sources = list(qs)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'[DRY RUN] ' if dry_run else ''}Running {len(sources)} source(s)…\n"
        ))

        wrangler = DataWrangler()
        deduplicator = Deduplicator()
        loader = PropertyLoader()

        for source in sources:
            self.stdout.write(f"  >> {source.name} ({source.scraper_class})")
            max_listings = max_listings_override or source.max_listings
            t0 = time.time()

            if not dry_run:
                job = ScrapeJob.objects.create(
                    source=source,
                    status='running',
                    triggered_by='management_command',
                    started_at=datetime.now(tz=tz.utc),
                )

            try:
                ScraperClass = get_scraper_class(source.scraper_class)
                scraper = ScraperClass(max_listings=max_listings)
                raw_records = scraper.scrape_all()
                self.stdout.write(f"     Scraped {len(raw_records)} raw records")

                if dry_run:
                    for r in raw_records[:3]:
                        self.stdout.write(f"       sample: {r.get('title', '?')[:60]}")
                    elapsed = time.time() - t0
                    self.stdout.write(self.style.SUCCESS(f"     [dry-run] done in {elapsed:.1f}s"))
                    continue

                imported = duplicates = normalized = failed = 0
                for raw in raw_records:
                    listing_url = str(raw.get('listing_url') or '')
                    title = str(raw.get('title') or '')
                    ext_id = build_external_id(source.name, listing_url, title)

                    listing, created = ScrapedListing.objects.get_or_create(
                        external_id=ext_id,
                        defaults={
                            'job': job,
                            'source': source,
                            'source_url': listing_url,
                            'status': 'raw',
                            'raw_data': raw,
                        },
                    )
                    if not created:
                        duplicates += 1
                        continue

                    silver = wrangler.wrangle(raw)
                    if not silver:
                        listing.status = 'failed'
                        listing.error_message = 'Wrangler returned None'
                        listing.save(update_fields=['status', 'error_message'])
                        failed += 1
                        continue

                    listing.normalized_data = silver
                    listing.normalized_at = datetime.now(tz=tz.utc)
                    listing.status = 'normalized'
                    listing.save(update_fields=['normalized_data', 'normalized_at', 'status'])
                    normalized += 1

                    dup = deduplicator.find_duplicate(ext_id, listing_url, silver)
                    if dup and dup.pk != listing.pk:
                        listing.status = 'duplicate'
                        listing.duplicate_of = dup
                        listing.save(update_fields=['status', 'duplicate_of'])
                        duplicates += 1
                        continue

                    try:
                        prop, _created = loader.load(listing)
                        listing.property = prop
                        listing.imported_at = datetime.now(tz=tz.utc)
                        listing.status = 'imported'
                        listing.save(update_fields=['property', 'imported_at', 'status'])
                        imported += 1
                    except Exception as exc:
                        listing.status = 'failed'
                        listing.error_message = str(exc)[:500]
                        listing.save(update_fields=['status', 'error_message'])
                        failed += 1

                source.last_scraped_at = datetime.now(tz=tz.utc)
                source.save(update_fields=['last_scraped_at'])

                job.records_scraped = len(raw_records)
                job.records_normalized = normalized
                job.records_imported = imported
                job.records_duplicates = duplicates
                job.records_failed = failed
                job.status = 'completed'
                job.finished_at = datetime.now(tz=tz.utc)
                job.save()

                elapsed = time.time() - t0
                self.stdout.write(
                    self.style.SUCCESS(
                        f"     imported={imported} dupes={duplicates} "
                        f"failed={failed} ({elapsed:.1f}s)"
                    )
                )

            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"     FAILED: {exc}"))
                if not dry_run and 'job' in dir():
                    job.status = 'failed'
                    job.error_log = str(exc)[:2000]
                    job.finished_at = datetime.now(tz=tz.utc)
                    job.save(update_fields=['status', 'error_log', 'finished_at'])

        self.stdout.write(self.style.SUCCESS('\nDone.\n'))
