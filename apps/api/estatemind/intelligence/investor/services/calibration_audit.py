"""
Hardening 1: Calibration Audit Service
=======================================

Quarterly audit that validates investment grades are calibrated correctly:
  - Do A-graded properties actually outperform D-graded properties?
  - Is the grade distribution monotonic (A > B > C > D by return)?
  - If not, which components need recalibration?
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import statistics

from django.utils import timezone
from django.db.models import Avg, StdDev, Count

from estatemind.intelligence.investor.models import InvestmentScore, CalibrationAuditRecord
from estatemind.market.core.models import DelegationMarketSnapshot

logger = logging.getLogger(__name__)


class CalibrationAuditService:
    """Quarterly calibration audit of investment grades."""
    MIN_GRADE_SAMPLES = 10     # measured returns per grade before it is compared
    MIN_SCORE_AGE_DAYS = 90    # a score's return is measured once it is this old


    LOOKBACK_MONTHS = 6
    MIN_SAMPLE_PER_GRADE = 30  # Minimum properties per grade for reliable testing

    def run_quarterly_audit(self) -> Dict[str, any]:
        """
        Run quarterly audit comparing predicted grades to realized returns.
        """
        try:
            audit_date = timezone.now().date()
            lookback_date = audit_date - timedelta(days=self.LOOKBACK_MONTHS * 30)

            # Scored properties from the lookback period, old enough for a
            # price change to mean something.
            scores = InvestmentScore.objects.filter(
                score_date__gte=lookback_date,
                score_date__lte=audit_date - timedelta(days=self.MIN_SCORE_AGE_DAYS),
            ).select_related('user')

            grade_buckets = self._group_by_grade(scores)
            grade_returns = self._compute_realized_returns(grade_buckets)
            is_monotonic, inversions = self._test_monotonicity(grade_returns)

            # Determine calibration status
            if is_monotonic is None:
                calibration_status = 'INSUFFICIENT_DATA'
                recommended_action = (
                    f'Not enough data to test grade calibration: fewer than two grades have '
                    f'{self.MIN_GRADE_SAMPLES}+ scored properties at least {self.MIN_SCORE_AGE_DAYS} days old. '
                    f'No weight changes suggested.')
            elif is_monotonic:
                calibration_status = 'PASS'
                recommended_action = 'Grades are well-calibrated. No changes needed.'
            else:
                # Check severity of inversions
                if len(inversions) > 2:
                    calibration_status = 'FAIL'
                    recommended_action = self._suggest_recalibration(grade_returns, inversions)
                else:
                    calibration_status = 'WARN'
                    recommended_action = self._suggest_recalibration(grade_returns, inversions)

            # Check sample size reliability
            reliability = self._assess_calibration_reliability(grade_returns)
            if is_monotonic is not None and not reliability['reliable']:
                calibration_status = 'WARN'
                if recommended_action:
                    recommended_action += f"\n{reliability['warning']}"
                else:
                    recommended_action = reliability['warning']

            # Create audit record
            audit_record = CalibrationAuditRecord.objects.create(
                audit_date=audit_date,
                lookback_months=self.LOOKBACK_MONTHS,
                grade_a_count=grade_returns['A']['count'],
                grade_a_mean_return=grade_returns['A']['mean_return'],
                grade_a_std_return=grade_returns['A']['std_return'],
                grade_b_count=grade_returns['B']['count'],
                grade_b_mean_return=grade_returns['B']['mean_return'],
                grade_b_std_return=grade_returns['B']['std_return'],
                grade_c_count=grade_returns['C']['count'],
                grade_c_mean_return=grade_returns['C']['mean_return'],
                grade_c_std_return=grade_returns['C']['std_return'],
                grade_d_count=grade_returns['D']['count'],
                grade_d_mean_return=grade_returns['D']['mean_return'],
                grade_d_std_return=grade_returns['D']['std_return'],
                is_monotonic=is_monotonic,
                calibration_status=calibration_status,
                inversions_detected=inversions,
                recommended_action=recommended_action,
                weights_before=self._get_current_weights(),
                weights_suggested=(self._get_suggested_weights(grade_returns, inversions)
                                   if is_monotonic is not None else {}),
            )

            return {
                'audit_id': audit_record.id,
                'audit_date': str(audit_date),
                'status': calibration_status,
                'monotonic': is_monotonic,
                'inversions': inversions,
                'grade_returns': grade_returns,
                'action': recommended_action,
            }

        except Exception as e:
            logger.error(f'Calibration audit error: {e}')
            return {'error': str(e)}

    def _group_by_grade(self, scores) -> Dict[str, List]:
        """Group scores by investment grade."""
        buckets = {'A': [], 'B': [], 'C': [], 'D': [], 'F': []}
        for score in scores:
            grade_letter = score.investment_grade[0]
            buckets[grade_letter].append(score)
        return buckets

    def _compute_realized_returns(self, grade_buckets: Dict[str, List]) -> Dict[str, Dict]:
        """
        Compute realized returns for each grade bucket.
        Realized return = (current_value - purchase_price) / purchase_price
        """
        result = {}
        for grade, scores in grade_buckets.items():
            returns = []
            for score in scores:
                if score.property_price_tnd > 0:
                    # Fetch current market price for the property's delegation
                    try:
                        latest_snapshot = DelegationMarketSnapshot.objects.filter(
                            delegation__name__iexact=score.delegation,
                        ).order_by('-as_of_date').first()

                        if latest_snapshot and latest_snapshot.median_price_per_sqm:
                            # Convert per sqm to total price estimate
                            # median_price_per_sqm is TND per m2
                            current_price = latest_snapshot.median_price_per_sqm * score.surface_m2
                        else:
                            current_price = score.property_price_tnd

                        # Simplified: assume no rental income for now
                        realized_return = (current_price - score.property_price_tnd) / score.property_price_tnd

                        returns.append(realized_return)
                    except Exception as e:
                        logger.warning(f'Error computing realized return for score {score.id}: {e}')
                        continue

            mean_return = statistics.mean(returns) if returns else 0.0
            std_return = statistics.stdev(returns) if len(returns) > 1 else 0.0

            result[grade] = {
                'count': len(returns),
                'mean_return': mean_return,
                'std_return': std_return,
                'returns': returns,
            }

        return result

    def _test_monotonicity(self, grade_returns: Dict[str, Dict]) -> Tuple[bool, List[str]]:
        """
        Test if returns follow monotonic pattern: A > B > C > D
        Returns: (is_monotonic, list of inversions)
        """
        inversions = []
        # Only grades with enough measured returns are compared; with fewer
        # than two such grades nothing can be concluded (None).
        grades = [g for g in ('A', 'B', 'C', 'D')
                  if grade_returns.get(g, {}).get('count', 0) >= self.MIN_GRADE_SAMPLES]
        if len(grades) < 2:
            return None, []
        for higher_grade, lower_grade in zip(grades, grades[1:]):
            if grade_returns[higher_grade]['mean_return'] < grade_returns[lower_grade]['mean_return']:
                inversions.append(f'{lower_grade}>{higher_grade}')
        return len(inversions) == 0, inversions

    def _suggest_recalibration(self, grade_returns: Dict, inversions: List[str]) -> str:
        """Suggest which opportunity score weights should be adjusted."""
        suggestions = []

        for inversion in inversions:
            if 'B>A' in inversion:
                suggestions.append(
                    'B properties outperformed A. Increase weights on '
                    'components that distinguish A from B (likely yield and undervaluation).'
                )
            elif 'C>B' in inversion:
                suggestions.append(
                    'C properties outperformed B. Reduce weight on yield component '
                    'which may be overvaluing low-yield A-grade properties.'
                )
            elif 'D>C' in inversion:
                suggestions.append(
                    'D properties outperformed C. Reduce weight on trend component '
                    'or increase weight on climate risk (which may be undervalued).'
                )

        action_str = ' '.join(suggestions) if suggestions else 'Review all component weights.'
        return action_str

    def _assess_calibration_reliability(self, grade_returns: Dict) -> Dict[str, any]:
        """
        Check if sample sizes are sufficient for reliable monotonicity testing.
        Returns reliability assessment with warning if samples too small.
        """
        low_count_grades = []
        for grade, data in grade_returns.items():
            if data['count'] < self.MIN_SAMPLE_PER_GRADE:
                low_count_grades.append(f"{grade}({data['count']})")

        if low_count_grades:
            return {
                'reliable': False,
                'warning': (
                    f"Grades with low sample counts: {', '.join(low_count_grades)}. "
                    f"Sample < {self.MIN_SAMPLE_PER_GRADE} per grade. "
                    f"Calibration conclusion is preliminary. Continue collecting data."
                ),
            }

        return {'reliable': True, 'warning': None}

    @staticmethod
    def _get_current_weights() -> Dict[str, float]:
        """Get current opportunity score weights."""
        from estatemind.intelligence.investor.services.scoring_chain import OpportunityScorerService
        return OpportunityScorerService.WEIGHTS

    @staticmethod
    def _get_suggested_weights(grade_returns: Dict, inversions: List[str]) -> Dict[str, float]:
        """Suggest adjusted weights based on audit results."""
        # Simple adjustment strategy: if low grades outperform, reduce trend weight
        # and increase undervaluation weight

        current = CalibrationAuditService._get_current_weights()

        if 'D>C' in inversions or 'C>B' in inversions:
            # Reduce trend weight
            current['trend'] = max(current['trend'] - 0.05, 0.10)
            current['undervaluation'] = min(current['undervaluation'] + 0.05, 0.40)
            # Renormalize
            total = sum(current.values())
            current = {k: v / total for k, v in current.items()}

        return current
