from unittest import mock

from django.test import TestCase

from estatemind.intelligence.investor.services import scorer, zone_data

ASSET = {'delegation': 'Nowhere', 'governorate': 'Tunis', 'property_type': 'apartment', 'surface_m2': 100,
         'acquisition_price_tnd': 300_000, 'current_value_tnd': 300_000}
OUTLOOK = {'available': True, 'source': 'forecast_module', 'growth_6m_pct': 1.8, 'growth_12m_pct': 3.7,
           'low_12m_pct': 1.0, 'high_12m_pct': 6.3, 'direction': 'UP'}


class ScoreAssetTests(TestCase):
    def test_no_rent_and_no_forecast_invent_nothing(self):
        result = scorer.score_asset(ASSET)
        self.assertIsNone(result['yield']['gross_yield_pct'])  # was 6% by default
        self.assertIsNone(result['irr']['irr_pct'])
        self.assertFalse(result['forecast']['available'])
        self.assertIsNone(result['forecast']['forecast_12m_pct'])  # was +6.0% 'UP'

    def test_rent_and_forecast_give_a_forward_irr_range(self):
        with mock.patch.object(zone_data, 'forecast_outlook', return_value=OUTLOOK):
            result = scorer.score_asset({**ASSET, 'monthly_rent_tnd': 1_250})
        self.assertEqual(result['yield']['basis'], 'your_rent')
        self.assertAlmostEqual(result['yield']['gross_yield_pct'], 5.0)
        self.assertAlmostEqual(result['yield']['net_yield_pct'], 5.0 * (1 - scorer.OPERATING_COST_SHARE), places=2)
        irr = result['irr']
        self.assertLess(irr['irr_low_pct'], irr['irr_pct'])
        self.assertLess(irr['irr_pct'], irr['irr_high_pct'])
        self.assertEqual(result['forecast']['forecast_12m_pct'], 3.7)

    def test_forward_irr_matches_a_hand_calculation(self):
        # no growth, no exit costs aside: IRR ~ net yield minus the exit cost spread
        self.assertAlmostEqual(scorer.forward_irr(100_000, 5_000, 0.0), 4.68, places=1)
