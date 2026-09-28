from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

SECRET = 'no such table: secret_internal_table'


class FriendlyErrorTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_drf_view_hides_exception_text(self):
        with mock.patch('estatemind.intelligence.climate.views.KrigingClimateService.get_instance',
                        side_effect=RuntimeError(SECRET)):
            response = self.client.get('/api/climate/point/', {'lat': 36.8, 'lon': 10.2})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(SECRET, response.content.decode())
        self.assertIn('reference', response.json())

    def test_unhandled_exception_in_drf_view_is_generic(self):
        with mock.patch('estatemind.intelligence.simulation.views.scenarios_list', side_effect=RuntimeError(SECRET)):
            response = self.client.get('/api/simulate/scenarios/')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(SECRET, response.content.decode())
        self.assertIn('Something went wrong', response.json()['error'])

    def test_simulation_start_database_error_is_generic(self):
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import RefreshToken
        user = get_user_model().objects.create_user(email='e@example.com', password='pw12345!x', full_name='E')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
        with mock.patch('estatemind.intelligence.simulation.views.SimulationRun.objects.create',
                        side_effect=Exception('table simulation_simulationrun has no column named owner_id')):
            response = self.client.post('/api/simulate/start/', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('owner_id', response.content.decode())
        self.assertIn('could not be started', response.json()['error'])

    def test_chatbot_market_reason_hides_exception_text(self):
        from estatemind.assistants.chatbot.services.market_data_retriever import MarketDataRetriever
        retriever = MarketDataRetriever.__new__(MarketDataRetriever)
        with mock.patch('estatemind.intelligence.forecast.models.DelegationForecast.objects.filter',
                        side_effect=RuntimeError(SECRET)):
            result = retriever._get_forecast_rankings('apartment')
        self.assertNotIn(SECRET, result['reason'])

    @override_settings(DEBUG=False)
    def test_non_drf_500_is_json(self):
        from config.urls import server_error
        response = server_error(None)
        self.assertEqual(response.status_code, 500)
        self.assertIn('Something went wrong', response.content.decode())
