from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from estatemind.intelligence.climate.services.composite_scorer import ClimateCompositeScorer


def _delegation(name='Test', governorate='Tunis', coastal=False, population=50_000):
    return SimpleNamespace(name=name, is_coastal=coastal, population=population,
                           region=SimpleNamespace(governorate=governorate))


class CompositeScorerTests(SimpleTestCase):
    """The normals-based scorer (data/climate_governorate_normals.csv)."""

    def test_score_is_bounded_with_consistent_interval(self):
        result = ClimateCompositeScorer().compute(_delegation())
        self.assertGreaterEqual(result['composite_score'], 0.0)
        self.assertLessEqual(result['composite_score'], 1.0)
        self.assertLessEqual(result['ci_lower_95'], result['composite_score'])
        self.assertGreaterEqual(result['ci_upper_95'], result['composite_score'])
        self.assertEqual(set(result['factors']), set(ClimateCompositeScorer.WEIGHTS))

    def test_flood_depends_on_the_place(self):
        # it used to take two fixed values, set only by the coastal flag
        scorer = ClimateCompositeScorer()
        flood = lambda gov, coastal=False: scorer.compute(_delegation(governorate=gov, coastal=coastal))['factors']['flood_risk']['score']  # noqa: E731
        self.assertGreater(flood('Jendouba'), flood('Tozeur'))          # Medjerda floods vs Saharan
        self.assertGreater(flood('Nabeul', coastal=True), flood('Nabeul'))

    def test_arid_south_is_not_the_lowest_risk(self):
        # Tozeur (heat 0.72 before) came out VERY_LOW; the south now carries heat and water stress
        scorer = ClimateCompositeScorer()
        tozeur = scorer.compute(_delegation('Tozeur', 'Tozeur'))
        bizerte = scorer.compute(_delegation('Bizerte Sud', 'Bizerte'))
        self.assertGreater(tozeur['factors']['water_stress']['score'], 0.9)
        self.assertGreater(tozeur['composite_score'], bizerte['composite_score'])
        self.assertNotEqual(tozeur['risk_label'], 'VERY_LOW')

    def test_every_governorate_has_normals(self):
        from estatemind.intelligence.climate.services.composite_scorer import _normals
        from estatemind.intelligence.valuation.inference.location import _reference
        self.assertEqual(set(_reference()[0].values()) - set(_normals()), set())

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
