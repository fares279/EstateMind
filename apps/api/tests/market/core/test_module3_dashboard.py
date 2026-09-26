from django.test import TestCase
from rest_framework.test import APIClient

from estatemind.market.core.models import Delegation, DelegationMarketSnapshot, MarketAnalyticsDaily, Region
from estatemind.market.core.tasks import materialize_daily_market_analytics
from estatemind.platform.users.models import User


class Module3DashboardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='module3@example.com',
            password='pass12345',
            plan='pro',
            role='pro',
        )
        self.client.force_authenticate(user=self.user)

        region = Region.objects.create(governorate='Tunis')
        delegation = Delegation.objects.create(region=region, name='La Marsa', population=100000)
        DelegationMarketSnapshot.objects.create(
            delegation=delegation,
            as_of_date='2026-05-01',
            listing_count=120,
            sale_listing_count=100,
            rent_listing_count=20,
            median_sale_price=420000,
            median_rent_price=1700,
            median_price_per_sqm=2400,
            median_days_on_market=38,
            forecast_6m=2550,
        )

    def test_materialization_task_creates_daily_row(self):
        result = materialize_daily_market_analytics()
        self.assertEqual(result.get('status'), 'completed')

    def test_kpi_freshness_endpoint(self):
        materialize_daily_market_analytics()
        response = self.client.get('/api/core/kpi-freshness/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('national_median_price', payload)

    def test_market_dashboard_endpoint(self):
        materialize_daily_market_analytics()
        response = self.client.get('/api/core/market-dashboard/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('national_median_price_sqm', payload)
        self.assertIn('freshness', payload)

    def test_materialized_median_matches_snapshot_median(self):
        materialize_daily_market_analytics()
        row = MarketAnalyticsDaily.objects.latest('date')
        raw_values = list(
            DelegationMarketSnapshot.objects
            .filter(as_of_date='2026-05-01')
            .values_list('median_price_per_sqm', flat=True)
        )
        raw_values = [float(v) for v in raw_values if v is not None]
        self.assertTrue(raw_values)

        raw_values.sort()
        mid = len(raw_values) // 2
        if len(raw_values) % 2 == 0:
            raw_median = (raw_values[mid - 1] + raw_values[mid]) / 2
        else:
            raw_median = raw_values[mid]

        delta_pct = abs(row.national_median_price_sqm - raw_median) / raw_median * 100
        self.assertLess(
            delta_pct,
            1.0,
            f'Materialized median deviates {delta_pct:.2f}% from snapshot median',
        )
