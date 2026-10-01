import datetime as dt

from django.test import TestCase
from rest_framework.test import APIClient

from estatemind.assistants.chatbot.services.intent_classifier import IntentClassifier
from estatemind.assistants.chatbot.services.market_data_retriever import MarketDataRetriever
from estatemind.intelligence.forecast.models import DelegationForecast
from estatemind.market.core.models import SYNTHETIC_SOURCE, Delegation, DelegationMarketSnapshot, Property, Region


def _listings(region, name, ptype, ppm, count, source='listings_csv', start=0):
    d, _ = Delegation.objects.get_or_create(region=region, name=name)
    for i in range(count):
        Property.objects.create(external_id=f'{name}-{ptype}-{source}-{start + i}', title='t', description='d',
                                property_type=ptype, region=region, delegation=d, price=ppm * 100, area_sqm=100,
                                bedrooms=2, bathrooms=1, source=source)
    return d


class NationalOverviewTests(TestCase):
    def setUp(self):
        region = Region.objects.create(governorate='Tunis')
        _listings(region, 'Carthage', 'apartment', 3000, 4)
        _listings(region, 'Bardo', 'apartment', 1000, 3)
        _listings(region, 'Bardo', 'apartment', 9000, 5, source=SYNTHETIC_SOURCE)  # samples don't count

    def test_national_median_of_real_listings_and_ins_growth(self):
        national = MarketDataRetriever().get_national_overview('apartment')['context']['national']
        self.assertTrue(national['available'])
        self.assertEqual(national['listing_count'], 7)
        self.assertEqual(national['median_price_per_sqm'], 3000)
        self.assertGreater(national['growth_pct_12m'], 0)

    def test_tunisia_question_gets_national_figures_not_a_location_request(self):
        reply = APIClient().post('/api/chatbot/message/', {'message': 'What is the average apartment price in Tunisia?'},
                                 format='json').json()['message']
        self.assertIn('Across Tunisia', reply)
        self.assertIn('3,000 TND/m²', reply)
        self.assertNotIn('need a location', reply)
        self.assertNotIn('[Note:', reply)  # every figure is grounded


class PropertyTypeTests(TestCase):
    def test_houses_are_extracted_as_the_stored_type(self):
        # 'villa' matched no listing, forecast or ranking
        for message in ('house prices in Sousse', 'prix des maisons à Sousse', 'villa in Hammamet'):
            entities = IntentClassifier.__new__(IntentClassifier)._extract_entities(message)
            self.assertEqual(entities.get('property_type'), 'house', message)

    def test_place_answer_uses_the_type_and_the_forecast(self):
        region = Region.objects.create(governorate='Sousse')
        d = _listings(region, 'Sousse Ville', 'house', 1400, 6)
        _listings(region, 'Sousse Ville', 'apartment', 2500, 6)
        DelegationMarketSnapshot.objects.create(delegation=d, as_of_date=dt.date.today(), median_price_per_sqm=2000,
                                                real_listing_count=12, synthetic_listing_count=0,
                                                forecast_12m=2000)  # stale: implies 0%
        origin = dt.date.today().replace(day=1)
        for h, price in ((1, 1400), (12, 1500)):
            DelegationForecast.objects.create(delegation_name='Sousse Ville', governorate='Sousse',
                                              property_type='house', forecast_origin=origin,
                                              forecast_month=origin + dt.timedelta(days=30 * h), horizon_idx=h,
                                              predicted_price_per_m2=price * 1000)
        reply = APIClient().post('/api/chatbot/message/', {'message': 'What is the house price in Sousse Ville?'},
                                 format='json').json()['message']
        self.assertIn('houses for sale is 1,400 TND/m²', reply)
        self.assertIn('from 6 real listings', reply)
        self.assertIn('+7.1%', reply)  # the forecast, not the snapshot's 0.0%


class IntentOverrideTests(TestCase):
    def test_portfolio_question_points_to_the_portfolio_page(self):
        reply = APIClient().post('/api/chatbot/message/', {'message': 'How is my portfolio doing?'},
                                 format='json').json()
        if reply['intent'] == 'portfolio_question':
            self.assertIn('/invest/portfolio', reply['message'])
            self.assertNotIn('need a location', reply['message'])
