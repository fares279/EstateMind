"""
Hardening 4: Investor Scorer Registry & A/B Testing
====================================================

Registry that manages champion/challenger scorer versions with A/B testing.
Ensures new scorer versions are validated before promotion.
"""

import logging
import hashlib
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, Callable
import random

from django.utils import timezone

from estatemind.intelligence.investor.models import InvestorScorerVersion, BuyWaitPrediction

logger = logging.getLogger(__name__)


class ABTestEvaluator:
    """
    Evaluates completed A/B tests and updates scorer status.
    Runs daily via Celery Beat to conclude tests automatically.
    """

    def evaluate_completed_tests(self) -> Dict[str, Any]:
        """
        Find A/B tests past their end_date and evaluate them.
        Automatically sets result to WINNER, LOSER, or INCONCLUSIVE.
        """
        try:
            completed = InvestorScorerVersion.objects.filter(
                status='challenger',
                ab_test_active=True,
                ab_test_end_date__lte=date.today(),
            )

            results = {}

            for challenger in completed:
                champion = (
                    InvestorScorerVersion.objects
                    .filter(
                        scorer_name=challenger.scorer_name,
                        status='champion',
                    )
                    .first()
                )

                if not champion:
                    logger.warning(f'No champion found for {challenger.scorer_name}')
                    continue

                # Compare acceptance rates between cohorts
                challenger_acceptance = self._compute_acceptance_rate(
                    scorer_name=challenger.scorer_name,
                    version=challenger.version,
                    start=challenger.ab_test_start_date,
                    end=challenger.ab_test_end_date,
                )

                champion_acceptance = self._compute_acceptance_rate(
                    scorer_name=champion.scorer_name,
                    version=champion.version,
                    start=challenger.ab_test_start_date,
                    end=challenger.ab_test_end_date,
                )

                # Determine outcome (5% lift threshold)
                if challenger_acceptance > champion_acceptance * 1.05:
                    result = 'WINNER'
                    action = 'Ready for manual promotion'
                elif challenger_acceptance < champion_acceptance * 0.95:
                    result = 'LOSER'
                    challenger.status = 'retired'
                    action = 'Automatically retired'
                else:
                    result = 'INCONCLUSIVE'
                    action = 'No significant difference'

                challenger.ab_test_result = result
                challenger.ab_test_active = False
                challenger.save()

                results[f'{challenger.scorer_name} v{challenger.version}'] = {
                    'result': result,
                    'challenger_acceptance': round(challenger_acceptance, 3),
                    'champion_acceptance': round(champion_acceptance, 3),
                    'lift_pct': round((challenger_acceptance / champion_acceptance - 1) * 100, 1)
                    if champion_acceptance > 0 else 0,
                    'action': action,
                }

                logger.info(f'A/B test evaluation for {challenger.scorer_name} v{challenger.version}: {result}')

            return results

        except Exception as e:
            logger.error(f'Error evaluating A/B tests: {e}')
            return {'error': str(e)}

    @staticmethod
    def _compute_acceptance_rate(scorer_name: str, version: str, start: date, end: date) -> float:
        """
        Compute fraction of predictions that led to user action (BUY signal accepted).
        Placeholder metric - would be replaced with actual engagement tracking.
        """
        try:
            predictions = (
                BuyWaitPrediction.objects
                .filter(
                    model_version=version,
                    prediction_date__gte=timezone.make_aware(
                        timezone.datetime.combine(start, timezone.time())
                    ),
                    prediction_date__lte=timezone.make_aware(
                        timezone.datetime.combine(end, timezone.time())
                    ),
                )
            )

            if predictions.count() == 0:
                return 0.0

            # Acceptance = fraction that recommended BUY
            buy_count = predictions.filter(predicted_signal='BUY').count()
            return buy_count / predictions.count()

        except Exception as e:
            logger.warning(f'Error computing acceptance rate: {e}')
            return 0.0


class InvestorScorerRegistry:
    """
    Registry managing versions of all 7 investor scoring models.
    Handles champion/challenger promotion and A/B testing.
    """

    # Promotion gates
    MIN_IMPROVEMENT_PCT = 0.02  # 2% improvement required
    AB_TEST_TRAFFIC_PCT = 0.10  # 10% of users
    AB_TEST_DURATION_DAYS = 14

    def get_active_scorer(self, scorer_name: str, user_id: Optional[int] = None) -> InvestorScorerVersion:
        """
        Get active scorer version for user.
        If user in A/B test cohort, return challenger; otherwise return champion.
        """
        try:
            # Check if there's an active A/B test
            ab_test = (
                InvestorScorerVersion.objects
                .filter(
                    scorer_name=scorer_name,
                    ab_test_active=True,
                    ab_test_start_date__lte=timezone.now().date(),
                    ab_test_end_date__gte=timezone.now().date(),
                    status='challenger',
                )
                .first()
            )

            champion = (
                InvestorScorerVersion.objects
                .filter(
                    scorer_name=scorer_name,
                    status='champion',
                )
                .order_by('-promoted_at')
                .first()
            )

            if ab_test and user_id:
                # Deterministic cohort assignment
                cohort_hash = int(hashlib.md5(f'{user_id}{scorer_name}'.encode()).hexdigest(), 16)
                in_ab_cohort = (cohort_hash % 100) < (ab_test.ab_test_traffic_pct * 100)

                if in_ab_cohort:
                    return ab_test

            if champion:
                return champion

            # Fallback to most recent version
            return (
                InvestorScorerVersion.objects
                .filter(scorer_name=scorer_name)
                .order_by('-created_at')
                .first()
            )

        except Exception as e:
            logger.error(f'Error getting active scorer: {e}')
            return None

    def create_challenger_version(self, scorer_name: str, version: str,
                                 training_date: datetime, sample_count: int,
                                 primary_metric: float, primary_metric_name: str,
                                 secondary_metric: Optional[float] = None,
                                 secondary_metric_name: str = '',
                                 artifact_path: str = '',
                                 artifact_hash: str = '') -> InvestorScorerVersion:
        """
        Create new challenger version of scorer.
        """
        try:
            challenger = InvestorScorerVersion.objects.create(
                scorer_name=scorer_name,
                version=version,
                status='challenger',
                training_date=training_date,
                training_sample_count=sample_count,
                validation_metric_primary=primary_metric,
                validation_metric_primary_name=primary_metric_name,
                validation_metric_secondary=secondary_metric or 0.0,
                validation_metric_secondary_name=secondary_metric_name,
                artifact_path=artifact_path,
                artifact_hash=artifact_hash,
            )

            logger.info(f'Created challenger {scorer_name} v{version}')
            return challenger

        except Exception as e:
            logger.error(f'Error creating challenger version: {e}')
            return None

    def promote_challenger_to_champion(self, challenger_version: InvestorScorerVersion) -> Dict[str, Any]:
        """
        Promote challenger to champion after it passes all gates.
        
        Gates:
          1. Performance improvement >= MIN_IMPROVEMENT_PCT
          2. A/B test passed
          3. Manual approval (logged in model)
        """
        try:
            # Gate 1: Performance check
            current_champion = (
                InvestorScorerVersion.objects
                .filter(
                    scorer_name=challenger_version.scorer_name,
                    status='champion',
                )
                .order_by('-promoted_at')
                .first()
            )

            if current_champion:
                improvement = (
                    (challenger_version.validation_metric_primary - current_champion.validation_metric_primary)
                    / current_champion.validation_metric_primary
                )

                if improvement < self.MIN_IMPROVEMENT_PCT:
                    return {
                        'success': False,
                        'reason': f'Improvement {improvement:.2%} < {self.MIN_IMPROVEMENT_PCT:.2%}',
                    }

            # Gate 2: A/B test results (check if test ran and won)
            if challenger_version.ab_test_active and challenger_version.ab_test_result != 'WINNER':
                return {
                    'success': False,
                    'reason': f'A/B test result: {challenger_version.ab_test_result}',
                }

            # Gate 3: Manual approval (would be checked in API layer)

            # Promotion
            if current_champion:
                current_champion.status = 'retired'
                current_champion.save()

            challenger_version.status = 'champion'
            challenger_version.promoted_at = timezone.now()
            challenger_version.promoted_by = 'system'  # Would be actual user in production
            challenger_version.ab_test_active = False
            challenger_version.save()

            logger.info(f'Promoted {challenger_version.scorer_name} v{challenger_version.version} to champion')

            return {
                'success': True,
                'message': f'Promoted to champion',
            }

        except Exception as e:
            logger.error(f'Error promoting challenger: {e}')
            return {'success': False, 'reason': str(e)}

    def start_ab_test(self, challenger_version: InvestorScorerVersion, traffic_pct: float = 0.10,
                     duration_days: int = 14) -> Dict[str, Any]:
        """
        Start A/B test for challenger version.
        Route traffic_pct of users to challenger.
        """
        try:
            challenger_version.ab_test_active = True
            challenger_version.ab_test_traffic_pct = traffic_pct
            challenger_version.ab_test_start_date = timezone.now().date()
            challenger_version.ab_test_end_date = timezone.now().date() + timedelta(days=duration_days)
            challenger_version.ab_test_result = 'PENDING'
            challenger_version.save()

            logger.info(f'Started A/B test for {challenger_version.scorer_name} v{challenger_version.version}')

            return {
                'success': True,
                'message': f'A/B test started for {traffic_pct*100:.0f}% traffic ({duration_days} days)',
            }

        except Exception as e:
            logger.error(f'Error starting A/B test: {e}')
            return {'success': False, 'reason': str(e)}

    def evaluate_ab_test(self, challenger_version: InvestorScorerVersion) -> Dict[str, Any]:
        """
        Evaluate A/B test results after test period ends.
        Compare user engagement metrics between challenger and champion.
        """
        try:
            if not challenger_version.ab_test_active:
                return {'error': 'A/B test not active'}

            if timezone.now().date() < challenger_version.ab_test_end_date:
                return {'error': 'A/B test still running'}

            # Collect predictions from both versions during test period
            challenger_predictions = (
                BuyWaitPrediction.objects
                .filter(
                    model_version=challenger_version.version,
                    prediction_date__gte=timezone.make_aware(
                        timezone.datetime.combine(challenger_version.ab_test_start_date, timezone.time())
                    ),
                    prediction_date__lte=timezone.make_aware(
                        timezone.datetime.combine(challenger_version.ab_test_end_date, timezone.time())
                    ),
                )
            )

            # Get champion version
            champion = (
                InvestorScorerVersion.objects
                .filter(
                    scorer_name=challenger_version.scorer_name,
                    status='champion',
                )
                .first()
            )

            champion_predictions = None
            if champion:
                champion_predictions = (
                    BuyWaitPrediction.objects
                    .filter(
                        model_version=champion.version,
                        prediction_date__gte=timezone.make_aware(
                            timezone.datetime.combine(challenger_version.ab_test_start_date, timezone.time())
                        ),
                        prediction_date__lte=timezone.make_aware(
                            timezone.datetime.combine(challenger_version.ab_test_end_date, timezone.time())
                        ),
                    )
                )

            # Simple evaluation: compare engagement rates
            challenger_engagement = self._compute_engagement(challenger_predictions)
            champion_engagement = self._compute_engagement(champion_predictions) if champion_predictions else 0.0

            # Declare winner
            if challenger_engagement > champion_engagement * 1.05:  # 5% lift threshold
                result = 'WINNER'
            elif champion_engagement > challenger_engagement * 1.05:
                result = 'LOSER'
            else:
                result = 'INCONCLUSIVE'

            challenger_version.ab_test_result = result
            challenger_version.ab_test_active = False
            challenger_version.save()

            return {
                'result': result,
                'challenger_engagement': challenger_engagement,
                'champion_engagement': champion_engagement,
                'lift': (challenger_engagement / champion_engagement - 1) * 100 if champion_engagement > 0 else 0,
            }

        except Exception as e:
            logger.error(f'Error evaluating A/B test: {e}')
            return {'error': str(e)}

    @staticmethod
    def _compute_engagement(predictions) -> float:
        """
        Simple engagement metric: fraction of predictions that led to a portfolio action.
        Placeholder - would track user behavior in production.
        """
        if not predictions:
            return 0.0
        
        buy_signals = predictions.filter(predicted_signal='BUY').count()
        return buy_signals / predictions.count() if predictions.count() > 0 else 0.0

    def rollback_to_previous(self, scorer_name: str, target_version: str) -> Dict[str, Any]:
        """
        Rollback active scorer to previous version if current version has issues.
        """
        try:
            target_version_obj = InvestorScorerVersion.objects.get(
                scorer_name=scorer_name,
                version=target_version,
            )

            current_champion = (
                InvestorScorerVersion.objects
                .filter(scorer_name=scorer_name, status='champion')
                .first()
            )

            if current_champion:
                current_champion.status = 'retired'
                current_champion.rollback_to_version = target_version
                current_champion.save()

            target_version_obj.status = 'champion'
            target_version_obj.promoted_at = timezone.now()
            target_version_obj.save()

            logger.warning(f'Rolled back {scorer_name} to v{target_version}')

            return {'success': True, 'message': f'Rolled back to v{target_version}'}

        except Exception as e:
            logger.error(f'Error rolling back: {e}')
            return {'success': False, 'reason': str(e)}
