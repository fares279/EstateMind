import datetime as dt

from django.test import TestCase

from estatemind.assistants.chatbot.services.market_data_retriever import MarketDataRetriever
from estatemind.intelligence.forecast.models import DelegationForecast
from estatemind.market.core.models import Delegation, DelegationClimateScore, DelegationMarketSnapshot, Region

TODAY = dt.date.today()


def _place(governorate, name, ppm, real, synthetic, growth_12m=1.05):
    region, _ = Region.objects.get_or_create(governorate=governorate)
    d = Delegation.objects.create(region=region, name=name, population=1000)
    DelegationMarketSnapshot.objects.create(
        delegation=d, as_of_date=TODAY, listing_count=real + synthetic, real_listing_count=real,
        synthetic_listing_count=synthetic, median_price_per_sqm=ppm, forecast_12m=ppm * growth_12m)
    for h in range(1, 13):
        DelegationForecast.objects.create(
            delegation_name=name, governorate=governorate, property_type='apartment',
            forecast_origin=dt.date(2026, 1, 1), forecast_month=dt.date(2026, h, 1), horizon_idx=h,
            predicted_price_per_m2=ppm * 1000 * (1 + 0.004 * (h - 1)))
    return d


class ChatbotGroundingTests(TestCase):
    def setUp(self):
        self.retriever = MarketDataRetriever.__new__(MarketDataRetriever)
        self.marsa = _place('Tunis', 'La Marsa', 2900, real=190, synthetic=0)
        _place('Tataouine', 'Tataouine Nord', 600, real=0, synthetic=3)
        _place('Tataouine', 'Tataouine Sud', 700, real=2, synthetic=3)

    def test_market_comes_from_snapshots_not_a_fixed_table(self):
        market = self.retriever._get_market_snapshot('la marsa', 'delegation')  # case-insensitive
        self.assertEqual((market['delegation'], market['median_price_per_sqm']), ('La Marsa', 2900))
        self.assertEqual((market['listing_count'], market['data_basis']), (190, 'listings'))
        self.assertAlmostEqual(market['trend_pct'], 5.0)

    def test_governorate_name_is_answered_at_governorate_level(self):
        market = self.retriever._get_market_snapshot('Tataouine', 'delegation')
        self.assertEqual((market['delegation'], market['median_price_per_sqm']), ('Tataouine', 650))
        self.assertEqual((market['listing_count'], market['data_basis']), (2, 'mixed'))

    def test_unknown_place(self):
        self.assertFalse(self.retriever._get_market_snapshot('Atlantis', 'delegation')['available'])

    def test_forecast_reads_the_real_growth(self):
        forecast = self.retriever._get_forecast('La Marsa', 'delegation')
        self.assertAlmostEqual(forecast['price_change_12m_pct'], 4.4, places=1)
        self.assertIsNone(forecast['confidence'])  # no invented confidence
        self.assertTrue(self.retriever._get_forecast('Tataouine', 'governorate')['available'])

    def test_investment_is_rule_based_scoring(self):
        invest = self.retriever._get_investment_context('La Marsa')
        self.assertTrue(invest['available'])
        self.assertEqual(invest['scoring_method'], 'rule_based')

    def test_chat_answers_say_when_figures_come_from_benchmarks(self):
        reply = self.client.post('/api/chatbot/message/', {'message': 'What is the average apartment price in Tataouine?'},
                                 content_type='application/json').json()
        if reply['intent'] == 'market_inquiry':
            self.assertIn("price benchmarks", reply['message'])

    def test_climate_question_retrieves_climate(self):
        DelegationClimateScore.objects.create(
            delegation=self.marsa, composite_score=0.2, composite_uncertainty=0.05, ci_lower_95=0.1, ci_upper_95=0.3,
            risk_label='LOW', flood_risk_score=0.3, flood_risk_uncertainty=0.05, heat_stress_score=0.4,
            heat_stress_uncertainty=0.05, coastal_erosion_score=0.5, coastal_erosion_uncertainty=0.05,
            infrastructure_resilience_score=0.3, infrastructure_resilience_uncertainty=0.05, wildfire_risk_score=0.1,
            wildfire_risk_uncertainty=0.05, computed_at=dt.datetime.now(dt.timezone.utc))
        reply = self.client.post('/api/chatbot/message/', {'message': 'What is the climate risk in La Marsa?'},
                                 content_type='application/json').json()
        if reply['intent'] == 'climate_question':
            self.assertIn('is low', reply['message'])
