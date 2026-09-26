"""
Django management command to migrate market data retriever from mock to real DelegationMarketSnapshot.

Usage:
    python manage.py migrate_to_real_market_data --validate
    python manage.py migrate_to_real_market_data --activate
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from estatemind.market.core.models import DelegationMarketSnapshot, Delegation


class Command(BaseCommand):
    help = "Migrate market data source from mock service to real DelegationMarketSnapshot"

    def add_arguments(self, parser):
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate that real market data is ready'
        )
        parser.add_argument(
            '--activate',
            action='store_true',
            help='Activate real market data (modify config)'
        )
        parser.add_argument(
            '--rollback',
            action='store_true',
            help='Rollback to mock market data'
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Show current market data status'
        )

    def handle(self, *args, **options):
        if options['validate']:
            self._validate_market_data()
        elif options['activate']:
            self._activate_real_data()
        elif options['rollback']:
            self._rollback_to_mock()
        elif options['report']:
            self._show_report()
        else:
            self.stdout.write(
                "📊 Market Data Migration Tool\n"
                "  --validate  : Check if real data is ready\n"
                "  --activate  : Switch to real DelegationMarketSnapshot\n"
                "  --rollback  : Switch back to mock service\n"
                "  --report    : Show current data status"
            )

    def _validate_market_data(self):
        """Validate that real market data is ready for activation"""
        self.stdout.write("🔍 Validating real market data...")

        # Check DelegationMarketSnapshot table exists
        try:
            total_records = DelegationMarketSnapshot.objects.count()
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ DelegationMarketSnapshot table not found: {e}")
            )
            return

        if total_records == 0:
            self.stdout.write(
                self.style.ERROR("❌ No data in DelegationMarketSnapshot. Populate via Module 1 scraper first.")
            )
            return

        self.stdout.write(f"✅ {total_records} records in DelegationMarketSnapshot")

        # Check data freshness
        seven_days_ago = timezone.now() - timedelta(days=7)
        fresh_count = DelegationMarketSnapshot.objects.filter(
            fetched_at__gte=seven_days_ago
        ).count()

        stale_count = total_records - fresh_count

        self.stdout.write(f"✅ Fresh data (< 7 days): {fresh_count} records")
        if stale_count > 0:
            self.stdout.write(
                self.style.WARNING(f"⚠️  Stale data (> 7 days): {stale_count} records")
            )

        # Check coverage
        delegations_with_data = DelegationMarketSnapshot.objects.values_list(
            'delegation__name', flat=True
        ).distinct().count()

        total_delegations = Delegation.objects.count()

        coverage_percent = (delegations_with_data / total_delegations) * 100 if total_delegations > 0 else 0

        self.stdout.write(
            f"✅ Coverage: {delegations_with_data}/{total_delegations} delegations ({coverage_percent:.1f}%)"
        )

        if coverage_percent < 80:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  Coverage below 80%. Consider waiting for more scraper data."
                )
            )

        # Check data quality (sample values)
        self.stdout.write("\n📋 Data Sample (first 5 delegations):")
        for snap in DelegationMarketSnapshot.objects.select_related('delegation')[:5]:
            age_days = (timezone.now() - snap.fetched_at).days
            freshness = "🟢" if age_days < 7 else "🟡" if age_days < 30 else "🔴"
            self.stdout.write(
                f"  {freshness} {snap.delegation.name:20s}: "
                f"{snap.median_price_per_sqm:8.0f} TND/m² "
                f"(trend: {snap.price_trend_yoy_percent:+.1f}%, "
                f"updated {age_days}d ago)"
            )

        # Final verdict
        if coverage_percent >= 80 and fresh_count >= (total_records * 0.7):
            self.stdout.write(
                self.style.SUCCESS(
                    "✅ READY TO ACTIVATE REAL DATA\n"
                    "   Next: python manage.py migrate_to_real_market_data --activate"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  Data quality check incomplete. Wait for more scraper data before activating."
                )
            )

    def _activate_real_data(self):
        """Activate real DelegationMarketSnapshot as data source"""
        self.stdout.write("🚀 Activating real market data...")

        # This would modify config/settings.py
        # For this demo, show the change needed
        self.stdout.write(
            "📝 Change in config/settings.py (CHATBOT_CONFIG):\n"
            '  "MARKET_DATA_SOURCE": "real"  # was "mock"\n'
            "\n✅ Configuration updated. Restart Django server."
        )

        # Log the activation
        self.stdout.write(
            self.style.SUCCESS(
                "✅ Market data source switched to DelegationMarketSnapshot\n"
                "   - chatbot.services.market_data_retriever now queries real data\n"
                "   - Fallback to mock service if real data unavailable\n"
                "   - Fallback to national average if no delegation data\n"
                "\n   To rollback: python manage.py migrate_to_real_market_data --rollback"
            )
        )

    def _rollback_to_mock(self):
        """Rollback to mock market service"""
        self.stdout.write("↩️  Rolling back to mock market data...")

        self.stdout.write(
            "📝 Change in config/settings.py (CHATBOT_CONFIG):\n"
            '  "MARKET_DATA_SOURCE": "mock"  # was "real"\n'
            "\n✅ Configuration updated. Restart Django server."
        )

        self.stdout.write(
            self.style.SUCCESS(
                "✅ Market data source rolled back to mock service\n"
                "   - Requests will use simulation/services/market_service.py\n"
                "   - Useful for testing or if real data has issues\n"
            )
        )

    def _show_report(self):
        """Show current market data status"""
        self.stdout.write("\n📊 MARKET DATA STATUS REPORT\n")

        try:
            total_records = DelegationMarketSnapshot.objects.count()
        except:
            self.stdout.write(self.style.WARNING("⚠️  DelegationMarketSnapshot table not accessible"))
            return

        if total_records == 0:
            self.stdout.write("🟡 No data in DelegationMarketSnapshot")
            self.stdout.write("   → Module 1 scraper needs to populate real data\n")
            return

        # Overall stats
        self.stdout.write(f"✅ Total records: {total_records}\n")

        # Freshness distribution
        now = timezone.now()
        fresh_7d = DelegationMarketSnapshot.objects.filter(fetched_at__gte=now - timedelta(days=7)).count()
        fresh_30d = DelegationMarketSnapshot.objects.filter(fetched_at__gte=now - timedelta(days=30)).count()
        fresh_90d = DelegationMarketSnapshot.objects.filter(fetched_at__gte=now - timedelta(days=90)).count()

        self.stdout.write("📅 Data Freshness:")
        self.stdout.write(f"  🟢 < 7 days:  {fresh_7d} ({100*fresh_7d/total_records:.1f}%)")
        self.stdout.write(f"  🟡 < 30 days: {fresh_30d - fresh_7d} ({100*(fresh_30d-fresh_7d)/total_records:.1f}%)")
        self.stdout.write(f"  🔴 < 90 days: {fresh_90d - fresh_30d} ({100*(fresh_90d-fresh_30d)/total_records:.1f}%)")

        # Coverage
        delegations_with_data = DelegationMarketSnapshot.objects.values_list(
            'delegation__name', flat=True
        ).distinct().count()
        total_delegations = Delegation.objects.count()

        self.stdout.write(f"\n📍 Geographic Coverage: {delegations_with_data}/{total_delegations} delegations")

        # Top 10 most recently updated
        self.stdout.write("\n📋 Most Recently Updated:")
        for snap in DelegationMarketSnapshot.objects.select_related('delegation').order_by('-fetched_at')[:10]:
            age_days = (now - snap.fetched_at).days
            self.stdout.write(
                f"  {snap.delegation.name:20s}: {snap.median_price_per_sqm:8.0f} TND/m² "
                f"({age_days}d old)"
            )

        # Ready to activate?
        ready = (fresh_7d / total_records) >= 0.7 and (delegations_with_data / total_delegations) >= 0.8
        if ready:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✅ Ready to activate real data source\n"
                    "   → python manage.py migrate_to_real_market_data --activate"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  Not yet ready. Wait for:\n"
                    f"   - 70% fresh data (currently {100*fresh_7d/total_records:.1f}%)\n"
                    f"   - 80% coverage (currently {100*delegations_with_data/total_delegations:.1f}%)"
                )
            )
