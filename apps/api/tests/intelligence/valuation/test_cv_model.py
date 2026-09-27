from django.test import SimpleTestCase

from estatemind.intelligence.valuation.inference.cv_model import CVModelService


class CVModelLoadTests(SimpleTestCase):
    def test_checkpoint_loads(self):
        # Regression: the wrapper had no load_state_dict, so loading always failed silently.
        service = CVModelService()
        if not service.model_path.exists():
            self.skipTest('image classifier artifact not present')
        self.assertIsNotNone(service._load_model())
        self.assertEqual(len(service._load_labels()), 3)
