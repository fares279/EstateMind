from unittest import mock

from django.test import SimpleTestCase, TestCase

from estatemind.intelligence.investor.services import market_rent, rent_model


class RentModelTests(SimpleTestCase):
    def test_no_artifact_means_no_prediction(self):
        with mock.patch.object(rent_model, '_model', return_value=None):
            self.assertIsNone(rent_model.predict('apartment', 'La Marsa', 'Tunis', 100))

    def test_land_is_never_rented(self):
        with mock.patch.object(rent_model, '_model', return_value=mock.Mock()):
            self.assertIsNone(rent_model.predict('land', 'La Marsa', 'Tunis', 300))


class MarketRentTests(TestCase):
    def test_model_estimate_is_used_when_available(self):
        with mock.patch.object(rent_model, 'predict', return_value=7.5) as predict:
            self.assertEqual(market_rent.market_rent_per_m2('La Marsa', 'Tunis', 'appartement', 120, 3, 2, 1),
                             (7.5, 'model'))
        predict.assert_called_once_with('apartment', 'La Marsa', 'Tunis', 120, 3, 2, 1)

    def test_falls_back_to_medians_without_a_model(self):
        with mock.patch.object(rent_model, 'predict', return_value=None):
            self.assertEqual(market_rent.market_rent_per_m2('Nowhere', 'Nowhere', 'apartment', 100), (None, 'none'))
