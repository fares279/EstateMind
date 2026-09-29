import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from estatemind.intelligence.investor.services.input_validation import InvalidListing, check_delegation, check_listing
from estatemind.market.core.models import Delegation, Region


class ScannerInputTests(TestCase):
    def setUp(self):
        tunis = Region.objects.create(governorate='Tunis')
        gabes = Region.objects.create(governorate='Gabès')
        Delegation.objects.create(region=tunis, name='La Marsa', apt_min_tnd=3000, apt_max_tnd=5800,
                                  land_min_tnd=800, land_max_tnd=3000)
        Delegation.objects.create(region=tunis, name='Carthage', apt_min_tnd=3500, apt_max_tnd=6000)
        Delegation.objects.create(region=gabes, name='Gabès Médina', land_min_tnd=5, land_max_tnd=1000,
                                  house_min_tnd=400, house_max_tnd=1200)
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create_user(
            email='inv@example.com', password='pw12345!x', full_name='I', plan='investor'))

    def test_delegation_matching_ignores_case_and_accents(self):
        self.assertEqual(check_delegation('tunis', 'carthage').name, 'Carthage')
        self.assertEqual(check_delegation('GABES', 'gabes medina').name, 'Gabès Médina')

    def test_delegation_from_another_governorate_is_rejected(self):
        with self.assertRaisesMessage(InvalidListing, 'La Marsa is in Tunis, not Gabès'):
            check_delegation('Gabès', 'La marsa')

    def test_absurd_and_unusual_prices(self):
        with self.assertRaises(InvalidListing):
            check_listing(5_000_000_000, 20, 'land', 'Gabès')
        with self.assertRaises(InvalidListing):
            check_listing(900_000, 20, 'land', 'Gabès')         # 45,000 TND/m2 vs 5-1,000
        self.assertEqual(check_listing(600_000, 120, 'apartment', 'Tunis', 'La Marsa'), [])
        self.assertEqual(len(check_listing(2_000_000, 120, 'apartment', 'Tunis', 'La Marsa')), 1)

    def test_scanner_rejects_nonsense_and_saves_real_values(self):
        bad = self.client.post('/api/investor/scanner/score/', {
            'listing_price_tnd': 5_000_000_000, 'surface_m2': 20, 'property_type': 'house',
            'governorate': 'Gabès', 'delegation': 'La marsa'}, format='json')
        self.assertEqual(bad.status_code, 400)
        self.assertNotIn('opportunity_score', bad.json())
        ok = self.client.post('/api/investor/scanner/score/', {
            'listing_price_tnd': 600_000, 'surface_m2': 120, 'property_type': 'apartment',
            'governorate': 'Tunis', 'delegation': 'La Marsa'}, format='json')
        self.assertEqual(ok.status_code, 200)
        self.assertIn(ok.json()['yield']['basis'], ('assumed', 'market_rent_delegation', 'market_rent_governorate'))
        row = self.client.get('/api/investor/scanner/history/').json()[0]
        self.assertEqual((row['delegation'], row['property_type'], row['listing_price_tnd']),
                         ('La Marsa', 'apartment', 600_000))

    def test_rule_based_label_follows_the_price_gap(self):
        from estatemind.intelligence.investor.services.scorer import score_listing
        cheap = score_listing({'listing_price_tnd': 50_000, 'surface_m2': 120, 'property_type': 'apartment',
                               'governorate': 'Tunis', 'delegation': 'La Marsa'})
        dear = score_listing({'listing_price_tnd': 3_000_000, 'surface_m2': 120, 'property_type': 'apartment',
                              'governorate': 'Tunis', 'delegation': 'La Marsa'})
        self.assertIn(cheap['undervaluation']['label'], ('UNDERVALUED', 'SEVERELY_UNDERVALUED'))
        self.assertEqual(dear['undervaluation']['label'], 'OVERPRICED')

    def test_monthly_rent_is_not_derived_from_the_price_when_market_rent_exists(self):
        from unittest import mock
        from estatemind.intelligence.investor.services import scorer
        with mock.patch.object(scorer, 'market_rent_per_m2', return_value=(8.0, 'delegation')):
            result = scorer.score_listing({'listing_price_tnd': 480_000, 'surface_m2': 100,
                                           'property_type': 'apartment', 'governorate': 'Tunis',
                                           'delegation': 'La Marsa'})
        self.assertEqual(result['yield']['monthly_rent_est'], 800)
        self.assertAlmostEqual(result['yield']['gross_yield_pct'], 2.0)

    def test_add_property_stores_canonical_names(self):
        response = self.client.post('/api/investor/portfolio/', {
            'property_name': 'Flat', 'property_type': 'apartment', 'governorate': 'tunis', 'delegation': 'carthage',
            'surface_m2': 100, 'acquisition_price_tnd': 450_000}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual((response.json()['delegation'], response.json()['governorate']), ('Carthage', 'Tunis'))
