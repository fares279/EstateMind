from django.test import SimpleTestCase

from estatemind.intelligence.investor.services import IRRCalculatorService
from estatemind.intelligence.investor.services.scoring_chain import PortfolioChain


class IRRScenarioLabelTests(SimpleTestCase):
    def test_zero_growth_is_labelled_identical(self):
        r = IRRCalculatorService().score(purchase_price_tnd=300_000, annual_rent_tnd=15_000, annual_appreciation_pct=0.0)
        self.assertEqual(r['irr_base_pct'], r['irr_pessimistic_pct'])
        self.assertEqual(r['irr_base_pct'], r['irr_optimistic_pct'])
        self.assertTrue(r['scenarios_identical'])
        self.assertIn('placeholder', r['scenario_note'])

    def test_real_growth_gives_distinct_scenarios(self):
        r = IRRCalculatorService().score(purchase_price_tnd=300_000, annual_rent_tnd=15_000, annual_appreciation_pct=4.0)
        self.assertLess(r['irr_pessimistic_pct'], r['irr_base_pct'])
        self.assertLess(r['irr_base_pct'], r['irr_optimistic_pct'])
        self.assertFalse(r['scenarios_identical'])

    def test_portfolio_with_placeholder_momentum_says_so(self):
        assets = [{'property_name': 'A', 'property_type': 'apartment', 'delegation': 'La Marsa', 'surface_m2': 100,
                   'room_count': 3, 'acquisition_price_tnd': 300_000, 'current_value_tnd': 300_000,
                   'is_self_managed': False, 'monthly_rent_tnd': 1_200}]
        market = {'La Marsa': {'delegation_median_monthly_rent': 1_200, 'delegation_price_momentum_12m': 0.0}}
        returns = PortfolioChain().run(portfolio_assets=assets, market_data_map=market)['returns']
        self.assertTrue(returns['irr_scenarios_identical'])
        self.assertIn('placeholder', returns['irr_scenario_note'])
