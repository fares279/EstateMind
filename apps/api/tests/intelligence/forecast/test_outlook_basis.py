from datetime import date

from django.core.management import call_command
from django.test import TestCase

from estatemind.intelligence.forecast.models import DelegationForecast
from estatemind.intelligence.forecast.services.forecast_service import get_market_data
from estatemind.market.core.models import Delegation, Region


class OutlookBasisTests(TestCase):
    def test_outlook_starts_this_month_and_claims_no_accuracy(self):
        call_command('generate_forecasts', verbosity=0)
        first = DelegationForecast.objects.order_by('forecast_month').first()
        self.assertEqual(first.forecast_month, date.today().replace(day=1))  # was a fixed Jan 2026
        self.assertFalse(DelegationForecast.objects.exclude(model_mape_pct=None).exists())

    def test_market_data_sends_coastal_flags_and_horizon(self):
        call_command('generate_forecasts', verbosity=0)
        region = Region.objects.create(governorate='Nabeul')
        Delegation.objects.create(region=region, name='Hammamet', is_coastal=True)
        data = get_market_data('apartment')
        row = next(d for d in data['delegations'] if d['delegation'] == 'Hammamet')
        self.assertTrue(row['is_coastal'])
        self.assertIn('start', data['horizon'])
