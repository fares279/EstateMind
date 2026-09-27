from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from estatemind.intelligence.climate.services.composite_scorer import ClimateCompositeScorer


def _delegation(name='Test', governorate='Tunis', coastal=False, population=50_000):
    return SimpleNamespace(name=name, is_coastal=coastal, population=population,
                           region=SimpleNamespace(governorate=governorate))


class CompositeScorerTests(SimpleTestCase):
    """Pins the current formula. Known domain issues (weights, coastal flags, mocked
    flood data) are documented for review, not asserted as correct here."""

    def test_score_is_bounded_with_consistent_interval(self):
        result = ClimateCompositeScorer().compute(_delegation())
        self.assertGreaterEqual(result['composite_score'], 0.0)
        self.assertLessEqual(result['composite_score'], 1.0)
        self.assertLessEqual(result['ci_lower_95'], result['composite_score'])
        self.assertGreaterEqual(result['ci_upper_95'], result['composite_score'])
        self.assertEqual(set(result['factors']), set(ClimateCompositeScorer.WEIGHTS))

    def test_flood_factor_depends_only_on_the_coastal_flag(self):
        scorer = ClimateCompositeScorer()
        inland = scorer.compute(_delegation(coastal=False))['factors']['flood_risk']['score']
        coastal = scorer.compute(_delegation(coastal=True))['factors']['flood_risk']['score']
        self.assertGreater(coastal, inland)
        # mocked: two fixed values, whatever the location
        self.assertEqual(inland, scorer.compute(_delegation('Other', 'Tozeur'))['factors']['flood_risk']['score'])

    def test_labels_follow_thresholds(self):
        label = ClimateCompositeScorer()._score_to_label
        self.assertEqual([label(x) for x in (0.1, 0.2, 0.4, 0.5, 0.7, 0.9)],
                         ['VERY_LOW', 'LOW', 'MODERATE', 'MODERATE_HIGH', 'HIGH', 'VERY_HIGH'])


class ClimateEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_unknown_delegation_is_404(self):
        self.assertEqual(self.client.get('/api/climate/delegation/Nowhere/').status_code, 404)

    def test_point_query_validates_coordinates(self):
        self.assertEqual(self.client.get('/api/climate/point/', {'lat': 'abc', 'lon': '10'}).status_code, 400)

    def test_point_query_falls_back_without_scores(self):
        result = self.client.get('/api/climate/point/', {'lat': 36.8, 'lon': 10.2}).json()
        self.assertEqual(result['method'], 'national_average_fallback')

    def test_empty_summary_and_heatmap(self):
        summary = self.client.get('/api/climate/summary/').json()
        self.assertEqual(summary['summary']['total_delegations'], 0)
        self.assertNotEqual(summary['timestamp'], '2026-05-19T00:00:00Z')
        self.assertEqual(self.client.get('/api/climate/heatmap/').json()['type'], 'FeatureCollection')

    def test_recalibration_is_admin_only(self):
        self.assertEqual(self.client.post('/api/climate/recalibrate/').status_code, 401)
        user = get_user_model().objects.create_user(email='u@example.com', password='pw12345!x', full_name='U')
        self.client.force_authenticate(user)
        self.assertEqual(self.client.post('/api/climate/recalibrate/').status_code, 403)
