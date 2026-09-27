import datetime as dt

from django.test import TestCase
from django.utils import timezone

from estatemind.intelligence.investor.models import CalibrationAuditRecord, InvestmentScore
from estatemind.intelligence.investor.services.calibration_audit import CalibrationAuditService
from estatemind.market.core.models import Delegation, DelegationMarketSnapshot, Region


def _score(grade, price, delegation, days_ago):
    score = InvestmentScore.objects.create(
        property_price_tnd=price, delegation=delegation, property_type='apartment', room_count=3, surface_m2=100,
        undervaluation_score=0, gross_yield_pct=5, net_yield_pct=4, yield_confidence='medium', buy_signal='WAIT',
        buy_signal_confidence=0.5, opportunity_score=50, investment_grade=grade, irr_base_pct=5,
        irr_pessimistic_pct=3, irr_optimistic_pct=7, risk_score=0.5, risk_label='medium',
    )
    # score_date is auto_now_add; backdate it explicitly
    InvestmentScore.objects.filter(pk=score.pk).update(score_date=timezone.now() - dt.timedelta(days=days_ago))
    return score


class CalibrationAuditTests(TestCase):
    def setUp(self):
        region = Region.objects.create(governorate='Tunis')
        # one delegation per grade, each now worth 2,000 TND/m2 (200,000 TND for 100 m2)
        for grade in 'ABCD':
            d = Delegation.objects.create(name=f'Deleg {grade}', region=region)
            DelegationMarketSnapshot.objects.create(delegation=d, as_of_date=dt.date(2026, 9, 1),
                                                    median_price_per_sqm=2000)

    def test_no_data_is_insufficient_not_an_inversion(self):
        result = CalibrationAuditService().run_quarterly_audit()
        self.assertEqual(result['status'], 'INSUFFICIENT_DATA')
        self.assertIsNone(result['monotonic'])
        self.assertEqual(result['inversions'], [])
        record = CalibrationAuditRecord.objects.get(id=result['audit_id'])
        self.assertEqual(record.weights_suggested, {})

    def test_recent_scores_are_not_used(self):
        for grade in 'ABCD':
            for _ in range(12):
                _score(grade, 150_000, f'Deleg {grade}', days_ago=10)
        self.assertEqual(CalibrationAuditService().run_quarterly_audit()['status'], 'INSUFFICIENT_DATA')

    def test_monotonic_grades_pass_and_returns_use_tnd_per_m2(self):
        # bought cheaper for better grades -> higher realized return (current value 200,000)
        for grade, price in zip('ABCD', (150_000, 160_000, 170_000, 180_000)):
            for _ in range(12):
                _score(grade, price, f'Deleg {grade}', days_ago=120)
        result = CalibrationAuditService().run_quarterly_audit()
        self.assertTrue(result['monotonic'])
        self.assertAlmostEqual(result['grade_returns']['A']['mean_return'], 200_000 / 150_000 - 1, places=6)

    def test_inversion_is_reported(self):
        for grade, price in zip('ABCD', (180_000, 170_000, 160_000, 150_000)):
            for _ in range(12):
                _score(grade, price, f'Deleg {grade}', days_ago=120)
        result = CalibrationAuditService().run_quarterly_audit()
        self.assertFalse(result['monotonic'])
        self.assertEqual(result['inversions'], ['B>A', 'C>B', 'D>C'])
