"""
Management command: process_pipeline

Re-processes existing ScrapedListings that are stuck in 'raw' or
'normalized' status through the remaining pipeline stages.

Usage
-----
# Process all raw → normalized → imported
python manage.py process_pipeline

# Limit to a specific status
python manage.py process_pipeline --status raw

# Limit records processed
python manage.py process_pipeline --limit 200

# Only re-run Silver → Gold for normalized records
python manage.py process_pipeline --status normalized
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Re-process ScrapedListings through remaining pipeline stages'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            choices=['raw', 'normalized', 'failed'],
            default=None,
            help='Only process listings with this status (default: raw + normalized)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='Max records to process (default: 500)',
        )
        parser.add_argument(
            '--source',
            type=str,
            default=None,
            help='Filter by source name',
        )

    def handle(self, *args, **options):
        from datetime import datetime, timezone
        from scraper.models import ScrapedListing
        from scraper.pipeline.wrangler import DataWrangler
        from scraper.pipeline.deduplicator import Deduplicator
        from scraper.pipeline.loader import PropertyLoader

        status_filter = options['status']
        limit = options['limit']
        source_filter = options['source']

        qs = ScrapedListing.objects.select_related('source')
        if status_filter:
            qs = qs.filter(status=status_filter)
        else:
            qs = qs.filter(status__in=['raw', 'normalized'])

        if source_filter:
            qs = qs.filter(source__name__iexact=source_filter)

        qs = qs.order_by('scraped_at')[:limit]
        listings = list(qs)
        total = len(listings)
        self.stdout.write(f"\nProcessing {total} record(s)…\n")

        wrangler = DataWrangler()
        deduplicator = Deduplicator()
        loader = PropertyLoader()

        normalized_count = imported_count = dup_count = failed_count = 0

        for listing in listings:
            # Stage 1: Raw → Silver
            if listing.status in ('raw', 'failed') and listing.raw_data:
                silver = wrangler.wrangle(listing.raw_data)
                if not silver:
                    listing.status = 'failed'
                    listing.error_message = 'Wrangler returned None'
                    listing.save(update_fields=['status', 'error_message'])
                    failed_count += 1
                    continue
                listing.normalized_data = silver
                listing.normalized_at = datetime.now(tz=timezone.utc)
                listing.status = 'normalized'
                listing.save(update_fields=['normalized_data', 'normalized_at', 'status'])
                normalized_count += 1

            # Stage 2: Deduplicate
            if listing.status == 'normalized':
                silver = listing.normalized_data or {}
                dup = deduplicator.find_duplicate(
                    listing.external_id, listing.source_url, silver
                )
                if dup and dup.pk != listing.pk:
                    listing.status = 'duplicate'
                    listing.duplicate_of = dup
                    listing.save(update_fields=['status', 'duplicate_of'])
                    dup_count += 1
                    continue

                # Stage 3: Silver → Gold
                try:
                    prop, _created = loader.load(listing)
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

        self.stdout.write(
            self.style.SUCCESS(
                f"Done — normalized={normalized_count} imported={imported_count} "
                f"duplicates={dup_count} failed={failed_count}\n"
            )
        )

        # Always run fix_properties after pipeline to ensure clean Gold layer
        self.stdout.write("Running fix_properties to clean and impute Gold-layer data…")
        from django.core.management import call_command
        call_command('fix_properties')
