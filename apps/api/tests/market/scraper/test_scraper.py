from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from estatemind.market.scraper.data_quality import SilverSchemaValidator
from estatemind.market.scraper.pipeline.wrangler import DataWrangler
from estatemind.market.scraper.scrapers.base import _parse_surface, normalize_tunisian_data

SALE = {'source': 'tayara', 'transaction_type': 'sale'}


class SurfaceParsingTests(SimpleTestCase):
    def test_units_separators_and_decimals(self):
        cases = {'120 m²': 120.0, '120m2': 120.0, '10000 m2': 10000.0, '12 500 m²': 12500.0,
                 '1 200m2': 1200.0, '85,5 m²': 85.5, 'S+2 3 pièces': None, 'm2': None}
        self.assertEqual({s: _parse_surface(s, '') for s in cases}, cases)

    def test_description_fallback(self):
        self.assertEqual(_parse_surface('', 'Bel appartement de 95 m2 au centre'), 95.0)


class NormalizeTests(SimpleTestCase):
    def test_numbers_already_parsed_by_the_scraper_are_kept(self):
        # tayara passes surface_area='' and the parsed number in surface_m2
        out = normalize_tunisian_data({**SALE, 'title': 'Appartement', 'price': '350 000 DT', 'price_tnd': 350000.0,
                                       'surface_area': '', 'surface_m2': 120.0})
        self.assertEqual((out['price_tnd'], out['surface_m2']), (350000.0, 120.0))

    def test_strings_are_parsed_when_numbers_are_missing(self):
        out = normalize_tunisian_data({**SALE, 'title': 'Terrain', 'price': '900 000 DT', 'surface_area': '10000 m2'})
        self.assertEqual((out['price_tnd'], out['surface_m2']), (900000.0, 10000.0))


class WranglerTests(SimpleTestCase):
    def setUp(self):
        self.wrangler = DataWrangler()

    def test_real_values_survive_to_silver(self):
        row = self.wrangler.wrangle({**SALE, 'listing_url': 'u1', 'title': 'Appartement S+2 à La Marsa',
                                     'price': '350 000 DT', 'price_tnd': 350000.0, 'surface_area': '',
                                     'surface_m2': 120.0, 'property_type': 'apartment'})
        self.assertEqual((row['price_tnd'], row['surface_m2']), (350000.0, 120.0))
        self.assertEqual((row['governorate'], row['delegation_hint']), ('Tunis', 'La Marsa'))
        self.assertEqual(row['price_per_m2'], round(350000 / 120, 2))

    def test_large_land_plot_is_kept(self):
        row = self.wrangler.wrangle({**SALE, 'listing_url': 'u2', 'title': 'Terrain à Hammamet',
                                     'price': '900 000 DT', 'surface_area': '10000 m2', 'property_type': 'land'})
        self.assertEqual((row['property_type'], row['surface_m2'], row['governorate']), ('land', 10000.0, 'Nabeul'))

    def test_listing_without_location_is_discarded(self):
        self.assertIsNone(self.wrangler.wrangle({**SALE, 'listing_url': 'u3', 'title': 'Appartement à vendre',
                                                 'description': 'sans localisation', 'price_tnd': 200000}))

    def test_record_id_is_stable(self):
        raw = {**SALE, 'listing_url': 'u4', 'title': 'Maison à Sfax', 'price': '300 000 DT', 'property_type': 'house'}
        self.assertEqual(self.wrangler.wrangle(raw)['record_id'], self.wrangler.wrangle(dict(raw))['record_id'])


class SilverSchemaTests(SimpleTestCase):
    def _record(self, **overrides):
        record = {'record_id': 'r1', 'source': 'tayara', 'listing_url': 'u', 'title': 'Appartement',
                  'transaction_type': 'sale', 'property_type': 'apartment', 'price_tnd': 250000.0,
                  'surface_m2': 100.0, 'governorate': 'Tunis'}
        record.update(overrides)
        return record

    def test_valid_record(self):
        self.assertEqual(SilverSchemaValidator().validate_record(self._record()), (True, []))

    def test_rejections(self):
        validator = SilverSchemaValidator()
        for bad in ({'governorate': 'Paris'}, {'price_tnd': 10}, {'transaction_type': 'swap'},
                    {'location_lat': 45.0, 'location_lon': 2.0}, {'title': None}):
            ok, errors = validator.validate_record(self._record(**bad))
            self.assertFalse(ok, bad)
            self.assertTrue(errors)


class ScraperAdminEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(email='u@example.com', password='pw12345!x', full_name='U')

    def test_pipeline_endpoints_are_admin_only(self):
        for method, url in [('post', '/api/scraper/jobs/trigger/'), ('post', '/api/scraper/pipeline/run/'),
                            ('get', '/api/scraper/stats/'), ('get', '/api/scraper/health/dashboard/'),
                            ('get', '/api/scraper/data-quality/violations/')]:
            self.client.force_authenticate(None)
            self.assertEqual(getattr(self.client, method)(url).status_code, 401, url)
            self.client.force_authenticate(self.user)
            self.assertEqual(getattr(self.client, method)(url).status_code, 403, url)


class ScraperHealthEndpointTests(TestCase):
    def test_health_reports_work_for_staff(self):
        # both raised NameError (timezone was only imported inside other functions)
        staff = get_user_model().objects.create_user(email='s@example.com', password='pw12345!x', full_name='S',
                                                     is_staff=True)
        client = APIClient()
        client.force_authenticate(staff)
        for url in ('/api/scraper/health/incidents/', '/api/scraper/health/scraper-agents/',
                    '/api/scraper/health/dashboard/', '/api/scraper/health/data-quality/'):
            self.assertEqual(client.get(url).status_code, 200, url)


class PriceUnitTests(SimpleTestCase):
    def test_md_means_thousands_of_dinars(self):
        from estatemind.market.scraper.scrapers.base import _parse_price
        self.assertEqual(_parse_price('350 MD'), 350_000.0)
        self.assertEqual(_parse_price('1,2 MD'), 1_200_000.0)      # MD also means millions
        self.assertEqual(_parse_price('1 200 000 MD'), 1_200_000.0)  # already in dinars
        self.assertEqual(_parse_price('350 000 DT'), 350_000.0)
        self.assertEqual(_parse_price('150 mille'), 150_000.0)

    def test_md_price_survives_the_wrangler(self):
        row = DataWrangler().wrangle({**SALE, 'listing_url': 'u9', 'title': 'Appartement S+2 à La Marsa',
                                      'price': '350 MD', 'surface_area': '120 m2', 'property_type': 'apartment'})
        self.assertEqual(row['price_tnd'], 350_000.0)
        self.assertNotIn('price', row['imputed'])


class ImputationFlagTests(TestCase):
    def test_filled_in_values_are_marked_on_the_property(self):
        from types import SimpleNamespace

        from estatemind.market.scraper.pipeline.loader import PropertyLoader
        row = DataWrangler().wrangle({**SALE, 'listing_url': 'u10', 'title': 'Appartement à La Marsa',
                                      'property_type': 'apartment'})
        self.assertEqual(set(row['imputed']), {'price', 'surface', 'bedrooms', 'bathrooms'})
        prop, _ = PropertyLoader().load(SimpleNamespace(normalized_data=row, external_id='ext-10'))
        self.assertTrue(prop.price_imputed and prop.area_imputed and prop.rooms_imputed)

    def test_measured_values_are_not_marked(self):
        from types import SimpleNamespace

        from estatemind.market.scraper.pipeline.loader import PropertyLoader
        row = DataWrangler().wrangle({**SALE, 'listing_url': 'u11', 'title': 'Appartement S+2 à La Marsa',
                                      'price': '350 000 DT', 'surface_area': '120 m2', 'property_type': 'apartment',
                                      'bedrooms': 2, 'bathrooms': 1})
        prop, _ = PropertyLoader().load(SimpleNamespace(normalized_data=row, external_id='ext-11'))
        self.assertFalse(prop.price_imputed or prop.area_imputed or prop.rooms_imputed)


class UnknownTownTests(SimpleTestCase):
    def test_no_town_means_no_delegation(self):
        # used to be the governorate's catch-all 'X Ville' delegation
        row = DataWrangler().wrangle({**SALE, 'listing_url': 'u12', 'title': 'Appartement à vendre',
                                      'governorate': 'Sousse', 'price': '250 000 DT', 'surface_area': '100 m2',
                                      'property_type': 'apartment'})
        self.assertIsNotNone(row)
        self.assertEqual(row['governorate'], 'Sousse')
        self.assertFalse(row['delegation_hint'])
