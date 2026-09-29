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

    def test_investment_ranking_without_listings_says_so(self):
        result = self.retriever._get_investment_rankings()
        self.assertFalse(result['available'])
        self.assertIn('No investment ranking data', result['reason'])


from estatemind.assistants.chatbot import views as chatbot_views  # noqa: E402
from estatemind.market.core.models import SYNTHETIC_SOURCE, Delegation, Property, Region  # noqa: E402


class RankingQuestionTests(TestCase):
    def test_ranking_words(self):
        for message in ('Which delegations will grow fastest?', 'cheapest areas to buy', 'Top 5 delegations',
                        'Where should I invest?'):
            self.assertTrue(chatbot_views._detect_ranking_query(message), message)
        self.assertFalse(chatbot_views._detect_ranking_query('What are prices in Sousse?'))

    def test_explicit_words_choose_the_ranking(self):
        context = {'market': {'available': True, 'source_tag': 'market_rankings', 'property_type': 'apartment',
                              'min_real_listings': 5,
                              'top_delegations': [{'delegation': 'Carthage', 'governorate': 'Tunis',
                                                   'median_price_per_sqm': 3209, 'listing_count': 17}],
                              'cheapest_delegations': [{'delegation': 'Fouchana', 'governorate': 'Ben Arous',
                                                        'median_price_per_sqm': 1171, 'listing_count': 6}]},
                   'forecast': {'available': True, 'top_delegations': [
                       {'delegation': 'Hergla', 'governorate': 'Sousse', 'growth_pct_12m': 13.7}]}}
        # classified as a forecast question, but it asks about prices
        text = chatbot_views._ranking_response('forecast_inquiry', 'Top 5 most expensive delegations', context)
        self.assertIn('Carthage', text)
        self.assertIn('Fouchana', chatbot_views._ranking_response('market_inquiry', 'cheapest areas', context))
        self.assertIn('Hergla', chatbot_views._ranking_response('market_inquiry', 'which will grow fastest', context))


class MarketRankingTests(TestCase):
    def setUp(self):
        self.retriever = MarketDataRetriever.__new__(MarketDataRetriever)
        region = Region.objects.create(governorate='Tunis')
        self.n = 0

        def listings(name, ppm, count, ptype='apartment', source='listings_csv'):
            d, _ = Delegation.objects.get_or_create(region=region, name=name)
            for _ in range(count):
                self.n += 1
                Property.objects.create(external_id=f'p{self.n}', title='t', description='d', property_type=ptype,
                                        region=region, delegation=d, price=ppm * 100, area_sqm=100, bedrooms=2,
                                        bathrooms=1, source=source)
        listings('Carthage', 3200, 6)
        listings('Bardo', 1200, 6)
        listings('Bardo', 150, 20, ptype='land')             # land must not drag Bardo's apartment median
        listings('Mornag', 900, 3)                           # too few real listings to rank
        listings('Mornag', 900, 10, source=SYNTHETIC_SOURCE) # sample listings don't count

    def test_ranks_real_listings_of_one_type(self):
        result = self.retriever._get_market_rankings('apartment')
        self.assertTrue(result['available'], result)
        self.assertEqual([r['delegation'] for r in result['top_delegations']], ['Carthage', 'Bardo'])
        self.assertEqual(result['cheapest_delegations'][0]['median_price_per_sqm'], 1200)
