import datetime as dt

from django.test import TestCase

from estatemind.assistants.chatbot.services.market_data_retriever import MarketDataRetriever
from estatemind.intelligence.forecast.models import DelegationForecast, DelegationPriceData

ORIGIN = dt.date(2026, 9, 1)


def _delegation(name, price_now, price_in_12m, origin=ORIGIN):
    DelegationPriceData.objects.get_or_create(
        delegation_name=name, governorate='Tunis', property_type='apartment',
        defaults=dict(price_min=price_now, price_avg=price_now, price_max=price_now, annual_trend_pct=0))
    for h in (1, 12):
        DelegationForecast.objects.create(
            delegation_name=name, governorate='Tunis', property_type='apartment', forecast_origin=origin,
            forecast_month=origin + dt.timedelta(days=30 * h), horizon_idx=h,
            predicted_price_per_m2=(price_now if h == 1 else price_in_12m) * 1000)


class ForecastRankingTests(TestCase):
    def setUp(self):
        self.retriever = MarketDataRetriever.__new__(MarketDataRetriever)

    def test_ranks_on_sqlite_across_all_delegations(self):
        # 25 delegations; the fastest grower sorts last alphabetically, beyond the old [:20] cut.
        for i in range(24):
            _delegation(f'Deleg {i:02d}', 2000, 2000 + i)
        _delegation('Zaouiet', 2000, 2400)
        result = self.retriever._get_forecast_rankings('apartment')
        self.assertTrue(result['available'], result)
        top = result['top_delegations'][0]
        self.assertEqual(top['delegation'], 'Zaouiet')
        self.assertAlmostEqual(top['growth_pct_12m'], 20.0)
        self.assertEqual(len(result['top_delegations']), 10)

    def test_uses_latest_origin_and_last_month(self):
        _delegation('Ariana', 2000, 2100, origin=dt.date(2026, 6, 1))
        _delegation('Ariana', 2000, 2200)
        top = self.retriever._get_forecast_rankings('apartment')['top_delegations'][0]
        self.assertAlmostEqual(top['growth_pct_12m'], 10.0)

    def test_investment_ranking_reports_not_implemented(self):
        result = self.retriever._get_investment_rankings()
        self.assertFalse(result['available'])
        self.assertIn('not implemented', result['reason'])
