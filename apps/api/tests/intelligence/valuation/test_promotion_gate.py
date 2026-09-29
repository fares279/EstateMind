from types import SimpleNamespace

from django.test import SimpleTestCase

from estatemind.intelligence.valuation.services.shap_stability_tester import SHAPStabilityTester

BASE = {'property_type': 'apartment', 'transaction_type': 'sale', 'governorate': 'Tunis',
        'city': 'El Menzah', 'size_m2': 120, 'bedrooms': 2, 'bathrooms': 1}


class _Bundle:
    """Stands in for InferenceBundle: attributions from a function of the mapped request."""

    def __init__(self, phi_for):
        self.phi_for = phi_for

    def predict(self, mapped, market_context):
        phi = self.phi_for(mapped)
        return SimpleNamespace(attributions={'base_log': 12.0, 'phi': phi} if phi is not None else None)


class ServedStabilityTests(SimpleTestCase):
    def test_stable_explanations_pass(self):
        bundle = _Bundle(lambda m: {'surface_m2': 0.5, 'city': 0.2, 'bedrooms': 0.05, 'transaction_type': 3.0})
        report = SHAPStabilityTester().run_served_stability_test(bundle, BASE, 'appartement')
        self.assertEqual(report['status'], 'pass')
        self.assertEqual(report['reference_ranking'], ['surface_m2', 'city', 'bedrooms'])

    def test_top_three_reordering_among_themselves_is_stable(self):
        # the top two swap whenever the surface is above 120 m2: about half the perturbations
        bundle = _Bundle(lambda m: {'surface_m2': 0.3 if m['surface_m2'] > 120 else 0.1, 'city': 0.2,
                                    'rooms': 0.05, 'bathrooms': 0.01})
        report = SHAPStabilityTester().run_served_stability_test(bundle, BASE, 'appartement')
        self.assertEqual(report['status'], 'pass')
        self.assertLess(report['exact_order_rate'], 0.75)

    def test_different_feature_entering_the_top_three_fails(self):
        # above 120 m2 'bathrooms' replaces 'rooms' in the top three: about half the perturbations
        bundle = _Bundle(lambda m: {'surface_m2': 0.5, 'city': 0.2,
                                    'rooms': 0.1 if m['surface_m2'] <= 120 else 0.01,
                                    'bathrooms': 0.15 if m['surface_m2'] > 120 else 0.02})
        report = SHAPStabilityTester().run_served_stability_test(bundle, BASE, 'appartement')
        self.assertEqual(report['status'], 'fail')

    def test_model_without_attributions_fails_closed(self):
        report = SHAPStabilityTester().run_served_stability_test(_Bundle(lambda m: None), BASE, 'appartement')
        self.assertEqual(report['status'], 'fail')
        self.assertIn('no SHAP attributions', report['recommendation'])

    def test_perturbation_goes_through_the_request_mapper(self):
        seen = []
        bundle = _Bundle(lambda m: seen.append(m) or {'surface_m2': 1.0, 'city': 0.1, 'rooms': 0.01})
        SHAPStabilityTester().run_served_stability_test(bundle, BASE, 'maison')
        self.assertEqual(len(seen), SHAPStabilityTester.N_SAMPLES + 1)
        self.assertTrue(all(m['model_property_type'] == 'maison' for m in seen))
        self.assertGreater(len({m['surface_m2'] for m in seen}), 50)
