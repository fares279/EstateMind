import io

from django.core.management import call_command
from django.test import TestCase

from estatemind.intelligence.forecast.models import DelegationForecast
from estatemind.intelligence.forecast.services.forecast_service import list_delegations_for_governorate
from estatemind.market.core.models import (
    SYNTHETIC_SOURCE, Delegation, DelegationClimateScore, DelegationMarketSnapshot, Property, Region,
)


class SeedDemoDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo_data', synthetic_per_type=1, stdout=io.StringIO())
        cls.counts = cls._counts()

    @staticmethod
    def _counts():
        return (Region.objects.count(), Delegation.objects.count(), Property.objects.count(),
                Property.objects.filter(source=SYNTHETIC_SOURCE).count(), DelegationMarketSnapshot.objects.count(),
                DelegationForecast.objects.count(), DelegationClimateScore.objects.count(),
                sorted(Property.objects.values_list('external_id', flat=True))[:50])

    def test_reference_geography(self):
        self.assertEqual(Region.objects.count(), 24)
        self.assertEqual(Delegation.objects.count(), 278)
        self.assertEqual(Delegation.objects.filter(centroid_lat__isnull=True).count(), 1)  # Hammamet: flagged gap
        tunis = Region.objects.get(governorate='Tunis')
        self.assertEqual(tunis.population, sum(tunis.delegations.values_list('population', flat=True)))

    def test_synthetic_rows_are_labelled_and_only_fill_gaps(self):
        synthetic = Property.objects.filter(source=SYNTHETIC_SOURCE)
        self.assertTrue(synthetic.exists())
        for p in synthetic[:200]:
            self.assertTrue(p.external_id.startswith('synthetic-'))
            self.assertIn('(synthetic)', p.title)
            self.assertIn('Not a real listing', p.description)
            self.assertEqual(p.transaction_type, 'sale')
            self.assertFalse(Property.objects.filter(source='listings_csv', transaction_type='sale',
                                                     delegation=p.delegation, property_type=p.property_type).exists())
        self.assertFalse(synthetic.filter(price__lt=20_000).exists())

    def test_real_rows_come_from_listings(self):
        real = Property.objects.exclude(source=SYNTHETIC_SOURCE)
        self.assertEqual(set(real.values_list('source', flat=True)), {'listings_csv'})
        self.assertTrue(real.filter(transaction_type='rent').exists())

    def test_snapshots_record_provenance_and_use_sale_prices(self):
        snap = DelegationMarketSnapshot.objects.filter(real_listing_count__gt=0).first()
        props = Property.objects.filter(delegation=snap.delegation)
        self.assertEqual(snap.real_listing_count, props.exclude(source=SYNTHETIC_SOURCE).count())
        self.assertEqual(snap.synthetic_listing_count, props.filter(source=SYNTHETIC_SOURCE).count())
        self.assertGreater(snap.median_price_per_sqm, 100)  # rents (~6 TND/m2) no longer mixed in
        self.assertTrue(DelegationMarketSnapshot.objects.exclude(forecast_12m=None).exists())

    def test_forecasts_and_climate(self):
        self.assertEqual(DelegationForecast.objects.count(), 278 * 4 * 12)
        self.assertEqual(DelegationClimateScore.objects.count(), 278)
        names = list_delegations_for_governorate('Tunis')
        self.assertEqual(len(names), len(set(names)))

    def test_rerun_changes_nothing(self):
        call_command('seed_demo_data', synthetic_per_type=1, stdout=io.StringIO())
        self.assertEqual(self._counts(), self.counts)
