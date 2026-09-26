"""
Django management command to clean up Property records with unrealistic prices.
Removes properties with asking_price > 1,000,000,000 TND (1 billion).

Usage:
    python manage.py cleanup_invalid_prices --dry-run  # Preview changes
    python manage.py cleanup_invalid_prices              # Apply deletion
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from estatemind.market.core.models import Property

class Command(BaseCommand):
    help = 'Remove Property records with price > 1,000,000,000 TND (unrealistic data artifacts)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Preview deletions without actually removing records',
        )
        parser.add_argument(
            '--max-price',
            type=float,
            default=1_000_000_000,
            help='Maximum allowed price in TND (default: 1,000,000,000)',
        )

    def handle(self, *args, **options):
        max_price = options['max_price']
        dry_run = options['dry_run']

        # Find all invalid records
        invalid_properties = Property.objects.filter(price__gt=max_price)
        count = invalid_properties.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(f'✓ No invalid properties found (all prices ≤ {max_price:,.0f} TND)')
            )
            return

        self.stdout.write(f'Found {count} properties with price > {max_price:,.0f} TND:')
        self.stdout.write('')

        # Show sample records
        samples = invalid_properties.values('id', 'title', 'price', 'delegation', 'created_at')[:10]
        for prop in samples:
            self.stdout.write(
                f"  ID {prop['id']}: {prop['title'][:50]} — {prop['price']:,.0f} TND "
                f"({prop['delegation']}, created {prop['created_at'].date()})"
            )

        if count > 10:
            self.stdout.write(f'  ... and {count - 10} more')

        self.stdout.write('')

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'[DRY-RUN] Would delete {count} properties. Run without --dry-run to confirm.')
            )
            return

        # Confirm deletion
        try:
            response = input(f'\nPermanently delete {count} properties? (yes/no): ')
            if response.lower() not in ('yes', 'y'):
                self.stdout.write(self.style.WARNING('Cancelled.'))
                return
        except (KeyboardInterrupt, EOFError):
            self.stdout.write(self.style.WARNING('Cancelled.'))
            return

        # Perform deletion
        deleted_count, _ = invalid_properties.delete()
        self.stdout.write(
            self.style.SUCCESS(f'✓ Deleted {deleted_count} properties with price > {max_price:,.0f} TND')
        )
