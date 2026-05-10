import csv
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from core.models import Delegation, Property, Region


class DelegationModelTests(TestCase):
    def test_delegation_creation_and_str(self):
        region = Region.objects.create(governorate="Tunis")
        delegation = Delegation.objects.create(
            region=region,
            name="La Soukra",
            population=50000,
        )

        self.assertEqual(delegation.name, "La Soukra")
        self.assertEqual(str(delegation), "La Soukra, Tunis")

    def test_delegation_unique_together(self):
        region = Region.objects.create(governorate="Ariana")
        Delegation.objects.create(region=region, name="Raoued", population=1000)

        with self.assertRaises(Exception):
            Delegation.objects.create(region=region, name="Raoued", population=2000)


class LoadDelegationsAndPropertiesCommandTests(TestCase):
    def _write_csv(self, path: Path, headers, rows):
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def test_command_imports_delegations_and_properties(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            delegations_csv = tmp_path / "delegations.csv"
            properties_csv = tmp_path / "properties.csv"

            self._write_csv(
                delegations_csv,
                headers=["Delegation", "Governorate", "Population"],
                rows=[
                    {"Delegation": "La Soukra", "Governorate": "Tunis", "Population": "123456"},
                ],
            )

            self._write_csv(
                properties_csv,
                headers=[
                    "record_id",
                    "source",
                    "title",
                    "transaction_type",
                    "property_type",
                    "price_tnd",
                    "surface_m2",
                    "price_per_m2",
                    "rooms",
                    "bedrooms",
                    "bathrooms",
                    "governorate",
                    "delegation",
                    "location_raw",
                    "posted_at",
                    "scraped_at",
                    "currency",
                ],
                rows=[
                    {
                        "record_id": "rec_1",
                        "source": "Local Agency",
                        "title": "Apartment in La Soukra",
                        "transaction_type": "sale",
                        "property_type": "Apartment",
                        "price_tnd": "250000",
                        "surface_m2": "100",
                        "price_per_m2": "2500",
                        "rooms": "3",
                        "bedrooms": "2",
                        "bathrooms": "1",
                        "governorate": "Tunis",
                        "delegation": "La Soukra",
                        "location_raw": "Tunis, La Soukra",
                        "posted_at": "2026-04-01",
                        "scraped_at": "2026-04-15",
                        "currency": "TND",
                    }
                ],
            )

            call_command(
                "load_delegations_and_properties",
                str(delegations_csv),
                str(properties_csv),
                verbosity=0,
            )

        self.assertEqual(Region.objects.count(), 1)
        self.assertEqual(Delegation.objects.count(), 1)
        self.assertEqual(Property.objects.count(), 1)

        prop = Property.objects.get(external_id="rec_1")
        self.assertEqual(prop.property_type, "apartment")
        self.assertEqual(prop.region.governorate, "Tunis")
        self.assertEqual(prop.delegation.name, "La Soukra")
        self.assertEqual(prop.price, 250000.0)
