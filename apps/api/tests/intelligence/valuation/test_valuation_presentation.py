import re

from django.test import SimpleTestCase, TestCase

from estatemind.intelligence.valuation.services import valuation_service
from estatemind.intelligence.valuation.services.labels import model_label, user_reasons
from estatemind.intelligence.valuation.services.nlp_service import is_readable

BASE = {'property_type': 'Appartement', 'transaction_type': 'sale', 'governorate': 'Tunis',
        'city': 'La Marsa', 'size_m2': 120, 'bedrooms': 3, 'bathrooms': 2}
CODE = re.compile(r'^[a-z_]+(:[a-z_]+)?$')  # e.g. reference_dataset_missing, ood:processor_unavailable


class LabelTests(SimpleTestCase):
    def test_internal_codes_never_reach_users(self):
        reasons = user_reasons(['ood:processor_unavailable', 'reference_dataset_missing', 'cv_analysis_error: boom',
                                'catboost_signal_adjustment_1.05', 'some_new_code', 'No images uploaded.'])
        self.assertEqual(reasons, ['No images uploaded.'])

    def test_model_label(self):
        self.assertEqual(model_label('valuation:appartement', 'catboost-artifact', '2026-09-28'),
                         'CatBoost (Apartment model)')  # auto-registered: training date unknown
        self.assertEqual(model_label(None, 'bytype__maison__catboost'), 'CatBoost (House model)')
        self.assertEqual(model_label('valuation:terrain', 'estate_v3', '2026-10-01'),
                         'CatBoost (Land model), trained 2026-10-01')

    def test_text_gate(self):
        self.assertFalse(is_readable('veryyyyyyyyyyyy goooooooooooood'))
        self.assertFalse(is_readable('xxxxx yyyyy zzzzz'))
        self.assertTrue(is_readable('Bel appartement lumineux avec vue sur mer'))
        self.assertTrue(is_readable('شقة جميلة قريبة من البحر'))


class ValuationPresentationTests(TestCase):
    def setUp(self):
        from estatemind.intelligence.valuation.inference.model_registry import ModelRegistry
        reg = ModelRegistry()
        handle = reg.maybe_load_bundle(reg.get_best_handle('appartement'))
        if handle is None or handle.bundle is None:
            self.skipTest('valuation artifacts not available')

    def test_garbage_description_is_not_analysed(self):
        result = valuation_service.estimate(dict(BASE, description='veryyyyyyyyyyyy goooooooooooood'))
        ta = result['text_analysis']
        self.assertEqual(ta['description_quality'], 'insufficient')
        self.assertEqual(ta['key_phrases'], [])
        self.assertIsNone(ta['sentiment_label'])
        self.assertNotIn('location_sentiment', ta)
        self.assertIn('too short or unclear', result['ai_explanation'])

    def test_explanation_is_plain_and_never_credits_sentiment(self):
        result = valuation_service.estimate(dict(BASE, description='Bel appartement lumineux avec vue sur mer, rénové.'))
        text = result['ai_explanation']
        for internal in ('CatBoost', 'bundle', 'tfidf', 'CV path', 'national_average', 'serving'):
            self.assertNotIn(internal, text)
        self.assertIn('does not change the estimate', text)
        self.assertTrue(result['technical_details'])

    def test_no_internal_codes_or_raw_names(self):
        result = valuation_service.estimate(dict(BASE))
        for item in result['uncertainty_reasons'] + result['warnings']:
            self.assertFalse(CODE.match(item), item)
        self.assertTrue(result['model_display_name'].startswith('CatBoost ('))
        for cf in result['counterfactuals']:
            self.assertNotIn('size_m2', cf['description'])

    def test_drivers_are_model_attributions(self):
        result = valuation_service.estimate(dict(BASE))
        features = {d['feature'] for d in result['features_impact']}
        self.assertNotIn('Comparable Listings', features)
        shap = result['shap']
        self.assertEqual(shap['method'], 'catboost_shap')
        self.assertEqual(shap['contributions'][-1]['running'], shap['predicted'])  # steps add up to the estimate
        self.assertEqual(shap['predicted'], result['estimated_price'])

    def test_scenarios_are_labelled_rules_of_thumb(self):
        for scenario in valuation_service.estimate(dict(BASE))['scenarios']:
            self.assertEqual(scenario['method'], 'rule_of_thumb')
            self.assertIsNone(scenario['confidence'])
            self.assertNotIn('comparable listing', scenario['why'])
