"""
Module 7: Unit Tests
Tests for all 7 scoring models, scoring chains, and hardening services.
"""

import pytest
from django.test import TestCase
from django.utils import timezone
import numpy as np
from datetime import datetime, date

from estatemind.intelligence.investor.models import (
    InvestmentScore, PortfolioAnalysis, InvestorScorerVersion,
)
from estatemind.intelligence.investor.services import (
    UndervaluationDetectorService,
    YieldEstimatorService,
    BuyWaitClassifierService,
    OpportunityScorerService,
    InvestmentGraderService,
    IRRCalculatorService,
    PortfolioRiskAssessorService,
)
from estatemind.intelligence.investor.services.scoring_chain import ScannerChain, PortfolioChain
from estatemind.intelligence.investor.services.calibration_audit import CalibrationAuditService
from estatemind.intelligence.investor.services.covariance_model import PortfolioCovarianceModel
from estatemind.intelligence.investor.services.offline_rl_classifier import OfflineRLBuyWaitClassifier
from estatemind.intelligence.investor.services.scorer_registry import InvestorScorerRegistry


class TestScoringModels(TestCase):
    """Test individual scoring models (M1-M7)."""

    def setUp(self):
        self.m1 = UndervaluationDetectorService()
        self.m2 = YieldEstimatorService()
        self.m3 = BuyWaitClassifierService()
        self.m4 = OpportunityScorerService()
        self.m5 = InvestmentGraderService()
        self.m6 = IRRCalculatorService()
        self.m7 = PortfolioRiskAssessorService()

    def test_undervaluation_detector(self):
        """M1: Detect undervaluation."""
        result = self.m1.score(
            asking_price_tnd=300000,
            delegation_median_price_m2=2500,
            surface_m2=120,
            condition='good',
            age_years=10,
            property_type='apartment',
        )

        self.assertIn('value', result)
        self.assertIn('label', result)
        self.assertIn('drivers', result)
        self.assertTrue(-0.5 <= result['value'] <= 0.5)

    def test_yield_estimator(self):
        """M2: Estimate yield."""
        result = self.m2.score(
            purchase_price_tnd=350000,
            delegation_median_monthly_rent=1400,
            surface_m2=120,
            room_count=3,
            property_type='apartment',
            is_self_managed=False,
        )

        self.assertIn('gross_yield_pct', result)
        self.assertIn('net_yield_pct', result)
        self.assertIn('estimated_monthly_rent', result)
        self.assertTrue(result['net_yield_pct'] < result['gross_yield_pct'])

    def test_buy_wait_classifier(self):
        """M3: Classify as BUY/WAIT/AVOID."""
        result = self.m3.score(
            delegation_price_momentum_12m=0.10,
            undervaluation_score=0.15,
            estimated_net_yield=4.0,
            climate_risk_score=0.4,
            national_interest_rate=8.0,
            delegation_dom=25.0,
        )

        self.assertIn('signal', result)
        self.assertIn(result['signal'], ['BUY', 'WAIT', 'AVOID'])
        self.assertIn('confidence', result)

    def test_opportunity_scorer(self):
        """M4: Score opportunity composite."""
        result = self.m4.score(
            undervaluation_score=0.10,
            net_yield_pct=3.5,
            delegation_price_momentum_12m=0.08,
            delegation_dom=30.0,
            climate_risk_score=0.5,
        )

        self.assertIn('value', result)
        self.assertTrue(0 <= result['value'] <= 100)
        self.assertIn('breakdown', result)

    def test_investment_grader(self):
        """M5: Assign investment grade."""
        result = self.m5.score(opportunity_score=75.0)

        self.assertIn('grade', result)
        self.assertIn(result['grade'], ['A', 'B', 'C', 'D', 'F'])

    def test_irr_calculator(self):
        """M6: Compute IRR scenarios."""
        result = self.m6.score(
            purchase_price_tnd=350000,
            annual_rent_tnd=16800,
            annual_appreciation_pct=5.0,
            annual_appreciation_low_pct=2.0,
            annual_appreciation_high_pct=8.0,
            holding_years=10,
        )

        self.assertIn('irr_base_pct', result)
        self.assertIn('irr_pessimistic_pct', result)
        self.assertIn('irr_optimistic_pct', result)
        # Optimistic > base > pessimistic
        self.assertTrue(result['irr_pessimistic_pct'] < result['irr_base_pct'] < result['irr_optimistic_pct'])

    def test_portfolio_risk_assessor(self):
        """M7: Assess portfolio risk."""
        result = self.m7.score(
            asset_grades=['A', 'B', 'C', 'B'],
            asset_values=[100000, 150000, 80000, 120000],
            delegations=['Ben Arous', 'Tunis', 'Sfax', 'Ben Arous'],
        )

        self.assertIn('risk_score', result)
        self.assertIn('risk_label', result)
        self.assertIn(result['risk_label'], ['low', 'medium', 'high'])


class TestScoringChains(TestCase):
    """Test scoring chain composition."""

    def setUp(self):
        self.property_data = {
            'asking_price_tnd': 350000,
            'surface_m2': 120,
            'property_type': 'apartment',
            'room_count': 3,
            'condition': 'good',
            'age_years': 10,
            'holding_years': 10,
        }

        self.market_data = {
            'delegation': 'Ben Arous',
            'delegation_median_price_m2': 2900,
            'delegation_median_monthly_rent': 1400,
            'delegation_price_momentum_12m': 0.08,
            'delegation_dom': 30,
            'climate_risk_score': 0.45,
            'national_interest_rate': 8.0,
        }

    def test_scanner_chain(self):
        """Test complete scanner chain."""
        scanner = ScannerChain()
        result = scanner.run(
            property_data=self.property_data,
            market_data=self.market_data,
        )

        self.assertNotIn('error', result)
        self.assertIn('investment_grade', result)
        self.assertIn('opportunity_score', result)
        self.assertIn('recommendation', result)
        self.assertIn('key_drivers', result)

    def test_portfolio_chain(self):
        """Test complete portfolio chain."""
        portfolio_chain = PortfolioChain()

        assets = [
            {**self.property_data, 'delegation': 'Ben Arous', 'acquisition_price_tnd': 350000, 'current_value_tnd': 380000},
            {**self.property_data, 'delegation': 'Tunis', 'acquisition_price_tnd': 300000, 'current_value_tnd': 320000},
        ]

        market_map = {
            'Ben Arous': {**self.market_data, 'delegation_median_monthly_rent': 1400},
            'Tunis': {**self.market_data, 'delegation_median_monthly_rent': 1500},
        }

        result = portfolio_chain.run(
            portfolio_assets=assets,
            market_data_map=market_map,
        )

        self.assertNotIn('error', result)
        self.assertIn('portfolio', result)
        self.assertIn('returns', result)
        self.assertIn('risk', result)


class TestHardeningServices(TestCase):
    """Test hardening services."""

    def test_calibration_audit_service(self):
        """Test calibration audit logic."""
        service = CalibrationAuditService()

        # Simulate grade returns
        grade_returns = {
            'A': {'count': 10, 'mean_return': 0.12, 'std_return': 0.05},
            'B': {'count': 15, 'mean_return': 0.10, 'std_return': 0.06},
            'C': {'count': 12, 'mean_return': 0.08, 'std_return': 0.07},
            'D': {'count': 8, 'mean_return': 0.05, 'std_return': 0.08},
        }

        is_monotonic, inversions = service._test_monotonicity(grade_returns)

        self.assertTrue(is_monotonic)
        self.assertEqual(len(inversions), 0)

    def test_covariance_model(self):
        """Test portfolio covariance computation."""
        model = PortfolioCovarianceModel(lookback_months=12)

        delegations = ['Ben Arous', 'Tunis', 'Sfax']
        weights = np.array([0.4, 0.35, 0.25])

        # Should complete without error (may return 0.12 default if no data)
        vol = model.compute_portfolio_volatility(weights, delegations)
        self.assertGreater(vol, 0)

        dr = model.compute_diversification_ratio(weights, delegations)
        self.assertGreaterEqual(dr, 1.0)

    def test_offline_rl_classifier_fallback(self):
        """Test offline RL classifier fallback (no model)."""
        classifier = OfflineRLBuyWaitClassifier()

        result = classifier.predict({
            'delegation_momentum_12m': 0.10,
            'opportunity_score': 75,
            'undervaluation_pct': 0.15,
            'estimated_net_yield': 4.0,
        })

        self.assertIn('signal', result)
        self.assertIn(result['signal'], ['BUY', 'WAIT', 'AVOID'])

    def test_scorer_registry(self):
        """Test scorer registry version management."""
        registry = InvestorScorerRegistry()

        # Create test version
        v = InvestorScorerVersion.objects.create(
            scorer_name='test_scorer',
            version='1.0',
            status='champion',
            training_date=timezone.now(),
            training_sample_count=100,
            validation_metric_primary=0.95,
            validation_metric_primary_name='accuracy',
        )

        # Get active scorer
        active = registry.get_active_scorer('test_scorer')
        self.assertEqual(active.version, '1.0')


class TestEndToEndScanning(TestCase):
    """End-to-end test of property scanning."""

    def test_complete_scan_flow(self):
        """Test complete scanner flow with all models."""
        scanner = ScannerChain()

        property_data = {
            'asking_price_tnd': 250000,
            'surface_m2': 100,
            'property_type': 'apartment',
            'room_count': 2,
            'condition': 'excellent',
            'age_years': 3,
        }

        market_data = {
            'delegation_median_price_m2': 2800,
            'delegation_median_monthly_rent': 1300,
            'delegation_price_momentum_12m': 0.12,
            'delegation_dom': 20,
            'climate_risk_score': 0.3,
            'national_interest_rate': 7.5,
        }

        result = scanner.run(property_data, market_data)

        # Verify all outputs present
        assert 'undervaluation' in result
        assert 'yield' in result
        assert 'buy_signal' in result
        assert 'opportunity' in result
        assert 'grade' in result
        assert 'irr' in result

        # Verify grades (grade result is a dict with 'grade' key)
        assert 'grade' in result['grade']
        grade_value = result['grade']['grade'][0]  # Get letter part (e.g., 'A' from 'A+')
        assert grade_value in ['A', 'B', 'C', 'D', 'F']


# Parametrized tests for sensitivity analysis
@pytest.mark.parametrize('price,expected_direction', [
    (200000, 'positive'),  # Undervalued
    (350000, 'neutral'),    # At market
    (450000, 'negative'),   # Overvalued
])
def test_undervaluation_price_sensitivity(price, expected_direction):
    """Test M1 sensitivity to asking price."""
    m1 = UndervaluationDetectorService()
    result = m1.score(
        asking_price_tnd=price,
        delegation_median_price_m2=3000,
        surface_m2=100,
        condition='good',
        age_years=10,
        property_type='apartment',
    )

    if expected_direction == 'positive':
        assert result['value'] > 0
    elif expected_direction == 'negative':
        assert result['value'] < 0


@pytest.mark.parametrize('signal,confidence', [
    ('BUY', 0.7),
    ('WAIT', 0.5),
    ('AVOID', 0.6),
])
def test_classifier_confidence(signal, confidence):
    """Test M3 produces appropriate confidence levels."""
    m3 = BuyWaitClassifierService()

    if signal == 'BUY':
        features = {
            'delegation_price_momentum_12m': 0.15,
            'undervaluation_score': 0.20,
            'estimated_net_yield': 5.0,
            'climate_risk_score': 0.20,
        }
    elif signal == 'WAIT':
        features = {
            'delegation_price_momentum_12m': 0.02,
            'undervaluation_score': 0.05,
            'estimated_net_yield': 2.5,
            'climate_risk_score': 0.30,
        }
    else:  # AVOID
        features = {
            'delegation_price_momentum_12m': 0.0,
            'undervaluation_score': 0.0,
            'climate_risk_score': 0.80,
            'estimated_net_yield': 1.5,
        }

    result = m3.score(**features)
    assert result['signal'] == signal
    assert result['confidence'] >= 0.4
