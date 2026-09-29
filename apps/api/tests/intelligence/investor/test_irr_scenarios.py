from django.test import SimpleTestCase

from estatemind.intelligence.investor.services import IRRCalculatorService
from estatemind.intelligence.investor.services.scoring_chain import PortfolioChain

BASE = dict(purchase_price_tnd=300_000, annual_rent_tnd=15_000)


class IRRScenarioTests(SimpleTestCase):
    def test_no_forecast_is_labelled(self):
        r = IRRCalculatorService().score(**BASE, annual_appreciation_pct=None)
        self.assertEqual(r['irr_base_pct'], r['irr_pessimistic_pct'])
        self.assertEqual(r['irr_base_pct'], r['irr_optimistic_pct'])
        self.assertTrue(r['scenarios_identical'])
        self.assertIn('No price forecast', r['scenario_note'])

    def test_forecast_without_band_is_labelled(self):
        r = IRRCalculatorService().score(**BASE, annual_appreciation_pct=4.0)
        self.assertTrue(r['scenarios_identical'])
        self.assertIn('no band', r['scenario_note'])

    def test_band_gives_ordered_scenarios(self):
        r = IRRCalculatorService().score(**BASE, annual_appreciation_pct=4.0,
                                         annual_appreciation_low_pct=1.0, annual_appreciation_high_pct=7.0)
        self.assertLess(r['irr_pessimistic_pct'], r['irr_base_pct'])
        self.assertLess(r['irr_base_pct'], r['irr_optimistic_pct'])
        self.assertFalse(r['scenarios_identical'])

    def test_falling_forecast_keeps_optimistic_above_pessimistic(self):
        # scenarios used to be 0% and 1.5x base: with -8% growth, 'optimistic' was -12%
        r = IRRCalculatorService().score(**BASE, annual_appreciation_pct=-8.0,
                                         annual_appreciation_low_pct=-10.0, annual_appreciation_high_pct=-6.0)
        self.assertLess(r['irr_pessimistic_pct'], r['irr_base_pct'])
        self.assertLess(r['irr_base_pct'], r['irr_optimistic_pct'])


class PortfolioChainScenarioTests(SimpleTestCase):
    ASSET = {'property_name': 'A', 'property_type': 'apartment', 'delegation': 'La Marsa', 'surface_m2': 100,
             'room_count': 3, 'acquisition_price_tnd': 300_000, 'current_value_tnd': 300_000,
             'is_self_managed': False, 'monthly_rent_tnd': 1_200}

    def _returns(self, market):
        from unittest import mock

        from estatemind.intelligence.investor.services import scorer
        with mock.patch.object(scorer, 'score_asset', return_value={'grade': 'B'}):
            return PortfolioChain().run(portfolio_assets=[self.ASSET], market_data_map={'La Marsa': market})['returns']

    def test_forecast_band_gives_distinct_portfolio_scenarios(self):
        returns = self._returns({'delegation_median_monthly_rent': 1_200, 'growth_12m_pct': 3.7,
                                 'growth_12m_low_pct': 1.0, 'growth_12m_high_pct': 6.3})
        self.assertFalse(returns['irr_scenarios_identical'])
        self.assertLess(returns['irr_pessimistic_pct'], returns['blended_irr_pct'])
        self.assertLess(returns['blended_irr_pct'], returns['irr_optimistic_pct'])

    def test_net_yield_is_not_discounted_twice(self):
        returns = self._returns({'delegation_median_monthly_rent': 1_200, 'growth_12m_pct': 3.7})
        # used to be the average net yield x 0.75
        self.assertLess(returns['blended_net_yield_pct'], returns['blended_gross_yield_pct'])
        self.assertGreater(returns['blended_net_yield_pct'], returns['blended_gross_yield_pct'] * 0.5)
