from django.test import TestCase, override_settings

from estatemind.intelligence.valuation.services import valuation_service

BASE = {'property_type': 'Appartement', 'transaction_type': 'sale', 'governorate': 'Tunis',
        'city': 'La Marsa', 'size_m2': 120, 'bedrooms': 3, 'bathrooms': 2}
DESCRIPTION = 'Magnifique appartement lumineux avec vue sur mer, entièrement rénové, cuisine équipée.'


class SentimentPriceGatingTests(TestCase):
    def _driver_names(self, result):
        return {c['feature'] for c in result['shap']['contributions']}

    @override_settings(VALUATION_SENTIMENT_PRICE_ADJUSTMENT=False)
    def test_description_does_not_move_price_by_default(self):
        plain = valuation_service.estimate(dict(BASE))
        described = valuation_service.estimate(dict(BASE, description=DESCRIPTION))
        self.assertEqual(plain['estimated_price'], described['estimated_price'])
        self.assertFalse(described['model_info']['text_signals_applied'])
        self.assertTrue(described['model_info']['text_signal_values'])  # still reported
        self.assertFalse({'Description sentiment', 'Description Quality'} & self._driver_names(described))

    @override_settings(VALUATION_SENTIMENT_PRICE_ADJUSTMENT=True)
    def test_flag_restores_the_multiplier(self):
        described = valuation_service.estimate(dict(BASE, description=DESCRIPTION))
        self.assertTrue(described['model_info']['text_signals_applied'])
