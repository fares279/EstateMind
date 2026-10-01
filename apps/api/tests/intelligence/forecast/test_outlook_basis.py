from datetime import date

from django.core.management import call_command
from django.test import TestCase

from estatemind.intelligence.forecast.models import DelegationForecast
from estatemind.intelligence.forecast.services import national_index
from estatemind.intelligence.forecast.services.forecast_service import get_market_data
from estatemind.market.core.models import Delegation, Region


class OutlookBasisTests(TestCase):
    def test_outlook_starts_this_month_and_reports_the_national_backtest_error(self):
        call_command('generate_forecasts', verbosity=0)
        first = DelegationForecast.objects.order_by('forecast_month').first()
        self.assertEqual(first.forecast_month, date.today().replace(day=1))  # was a fixed Jan 2026
        apt = DelegationForecast.objects.filter(property_type='apartment').first()
        self.assertEqual(apt.model_version, 'ins_national_trend')
        self.assertEqual(apt.model_mape_pct, national_index.backtest('apartment')['mae_12m_pp']['avg_all'])

    def test_flat_benchmark_delegation_grows_at_the_national_rate(self):
        call_command('generate_forecasts', verbosity=0)
        rows = {r.horizon_idx: r.predicted_price_per_m2 for r in
                DelegationForecast.objects.filter(delegation_name='Ariana Ville', property_type='land')}
        # Ariana Ville land: benchmark trend -8%, median trend 0% -> national rate - 8 points
        expected = national_index.expected_annual_growth_pct('land') - 8
        self.assertAlmostEqual((rows[12] / rows[1]) ** (12 / 11) - 1, expected / 100, places=3)

    def test_market_data_sends_coastal_flags_and_horizon(self):
        call_command('generate_forecasts', verbosity=0)
        region = Region.objects.create(governorate='Nabeul')
        Delegation.objects.create(region=region, name='Hammamet', is_coastal=True)
        data = get_market_data('apartment')
        row = next(d for d in data['delegations'] if d['delegation'] == 'Hammamet')
        self.assertTrue(row['is_coastal'])
        self.assertIn('start', data['horizon'])
