from django.test import TestCase
from rest_framework.test import APIClient

from estatemind.market.core.models import Delegation, Property, Region
from estatemind.platform.users.models import User


class MapApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="pro@example.com",
            password="pass12345",
            plan="pro",
            role="pro",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)

        self.region = Region.objects.create(governorate="Tunis", latitude=36.8, longitude=10.2)
        self.delegation = Delegation.objects.create(
            region=self.region,
            name="La Soukra",
            population=100000,
            centroid_lat=36.87,
            centroid_lon=10.25,
        )

        Property.objects.create(
            external_id="p_1",
            title="Apartment A",
            description="Apartment A | Type: sale | Location: Tunis, La Soukra | Source: Local Agency",
            property_type="apartment",
            region=self.region,
            delegation=self.delegation,
            price=200000,
            area_sqm=100,
            bedrooms=2,
            bathrooms=1,
            latitude=36.87,
            longitude=10.25,
            source="Local Agency",
            is_active=True,
        )
        Property.objects.create(
            external_id="p_2",
            title="Apartment B",
            description="Apartment B | Type: rent | Location: Tunis, La Soukra | Source: Tayara",
            property_type="apartment",
            region=self.region,
            delegation=self.delegation,
            price=1500,
            area_sqm=80,
            bedrooms=2,
            bathrooms=1,
            latitude=36.871,
            longitude=10.251,
            source="Tayara",
            is_active=True,
        )

    def test_map_summary_endpoint(self):
        response = self.client.get("/api/map/summary/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_listings", data)
        self.assertIn("total_delegations", data)
        self.assertIn("avg_price_national", data)
        self.assertIn("delegations_kpis", data)

    def test_map_delegations_endpoint(self):
        response = self.client.get("/api/map/delegations/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(isinstance(data, list))
        self.assertGreaterEqual(len(data), 1)
        self.assertIn("delegation_name", data[0])
        self.assertIn("opportunity_score", data[0])

    def test_map_listings_endpoint_with_filters(self):
        response = self.client.get(
            "/api/map/listings/",
            {
                "governorate": "Tunis",
                "delegation": "La Soukra",
                "property_type": "apartment",
                "price_min": "1000",
                "price_max": "300000",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_count", data)
        self.assertIn("results", data)
        self.assertGreaterEqual(data["total_count"], 1)

    def test_map_heat_endpoints(self):
        price_response = self.client.get("/api/map/heat/price/")
        self.assertEqual(price_response.status_code, 200)
        price_data = price_response.json()
        self.assertEqual(price_data.get("type"), "FeatureCollection")
        self.assertIn("features", price_data)

        demand_response = self.client.get("/api/map/heat/demand/")
        self.assertEqual(demand_response.status_code, 200)
        demand_data = demand_response.json()
        self.assertEqual(demand_data.get("type"), "FeatureCollection")
        self.assertIn("features", demand_data)

    def test_map_opportunities_endpoint(self):
        response = self.client.get("/api/map/opportunities/", {"min_score": "0"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(isinstance(data, list))
        self.assertGreaterEqual(len(data), 1)
        self.assertIn("opportunity_score", data[0])
        self.assertIn("centroid_lat", data[0])
        self.assertIn("centroid_lon", data[0])
        self.assertIn("top_drivers", data[0])
        self.assertIn("confidence_level", data[0])
        self.assertIn("uncertainty_band_pct", data[0])

    def test_map_intelligence_audit_endpoint(self):
        response = self.client.get("/api/map/intelligence/audit/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("weights", data)


class ListingDealAssessmentTests(TestCase):
    def setUp(self):
        from estatemind.market.core.models import Delegation, Property, Region
        region = Region.objects.create(governorate='Tunis')
        self.d = Delegation.objects.create(region=region, name='La Marsa')
        for i, ppm in enumerate([2800, 2900, 3000, 3100, 3200]):
            Property.objects.create(external_id=f'c{i}', title=f'c{i}', description='', property_type='apartment',
                                    transaction_type='sale', region=region, delegation=self.d, price=ppm * 100,
                                    area_sqm=100, source='listings_csv')
        Property.objects.create(external_id='cheap', title='cheap', description='', property_type='apartment',
                                transaction_type='sale', region=region, delegation=self.d, price=200_000,
                                area_sqm=100, source='listings_csv')
        Property.objects.create(external_id='land', title='land', description='', property_type='land',
                                transaction_type='sale', region=region, delegation=self.d, price=100_000,
                                area_sqm=500, source='listings_csv')

    def test_listings_are_assessed_against_real_comparables(self):
        from rest_framework.test import APIClient
        rows = {r['external_id']: r for r in APIClient().get('/api/map/listings/').json()['results']}
        self.assertEqual(rows['cheap']['deal'], 'good')          # 2,000/m2 vs a 2,950 median
        self.assertEqual(rows['c2']['deal'], 'fair')
        self.assertEqual(rows['cheap']['deal_median_ppm'], 2950)  # median of all six
        self.assertIsNone(rows['land']['deal'])                  # one land listing: not assessed
        self.assertEqual(rows['cheap']['transaction_type'], 'sale')
