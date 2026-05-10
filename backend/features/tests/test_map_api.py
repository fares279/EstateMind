from django.test import TestCase

from core.models import Delegation, Property, Region


class MapApiTests(TestCase):
    def setUp(self):
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
