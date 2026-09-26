from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from estatemind.market.core.services.dashboard_kpi import record_kpi_freshness
from estatemind.intelligence.investor.models import PortfolioAsset


@shared_task(name='investor.materialize_daily_investor_summary')
def materialize_daily_investor_summary() -> dict:
    """Track investor summary freshness metadata for dashboard cards."""
    asset_count = PortfolioAsset.objects.count()
    record_kpi_freshness(
        kpi_name='top_yield_delegations',
        source_app='investor',
        row_count=asset_count,
        notes=f'Investor summary refreshed on {timezone.localdate()}',
    )
    return {
        'status': 'completed',
        'date': str(timezone.localdate()),
        'rows': asset_count,
    }


# Module 7: Portfolio & Investment Intelligence Governance Tasks
import logging

logger = logging.getLogger(__name__)


@shared_task(name='estatemind.intelligence.investor.tasks.run_calibration_audit')
def run_calibration_audit():
    """
    Quarterly: validates that grade A outperforms grade B, etc.
    Flags miscalibration and logs suggested weight adjustments.
    """
    try:
        from estatemind.intelligence.investor.services.calibration_audit import CalibrationAuditService
        service = CalibrationAuditService()
        result = service.run_quarterly_audit()
        logger.info(f'Calibration audit complete: {result}')
        return result
    except Exception as e:
        logger.error(f'Calibration audit failed: {e}', exc_info=True)
        raise


@shared_task(name='estatemind.intelligence.investor.tasks.evaluate_completed_ab_tests')
def evaluate_completed_ab_tests():
    """
    Daily: evaluates A/B tests that have passed their end_date.
    Sets ab_test_result to WINNER, LOSER, or INCONCLUSIVE.
    Automatically retires LOSER versions.
    """
    try:
        from estatemind.intelligence.investor.services.scorer_registry import ABTestEvaluator
        evaluator = ABTestEvaluator()
        result = evaluator.evaluate_completed_tests()
        logger.info(f'A/B test evaluation complete: {result}')
        return result
    except Exception as e:
        logger.error(f'A/B test evaluation failed: {e}', exc_info=True)
        raise


@shared_task(name='estatemind.intelligence.investor.tasks.check_rl_classifier_precision')
def check_rl_classifier_precision():
    """
    Monthly: checks buy/wait classifier precision on recent predictions.
    Queues retraining if precision drops below 0.70 threshold.
    """
    try:
        from estatemind.intelligence.investor.services.offline_rl_classifier import (
            OfflineRLBuyWaitClassifier
        )
        classifier = OfflineRLBuyWaitClassifier()
        if hasattr(classifier, 'check_precision_and_trigger_retrain'):
            result = classifier.check_precision_and_trigger_retrain()
        else:
            logger.info('RL classifier precision check - method not yet implemented')
            result = {'status': 'pending', 'note': 'Method not yet implemented'}
        logger.info(f'RL classifier precision check: {result}')
        return result
    except Exception as e:
        logger.error(f'RL classifier precision check failed: {e}', exc_info=True)
        raise


@shared_task(name='estatemind.intelligence.investor.tasks.sync_scorer_registry')
def sync_scorer_registry():
    """
    Weekly: ensures registry has at least one champion per scorer type.
    Promotes challengers that have won their A/B tests.
    """
    try:
        from estatemind.intelligence.investor.services.scorer_registry import InvestorScorerRegistry
        registry = InvestorScorerRegistry()
        if hasattr(registry, 'sync_champions'):
            result = registry.sync_champions()
        else:
            logger.info('Scorer registry sync - method not yet implemented')
            result = {'status': 'pending', 'note': 'Method not yet implemented'}
        logger.info(f'Scorer registry sync complete: {result}')
        return result
    except Exception as e:
        logger.error(f'Scorer registry sync failed: {e}', exc_info=True)
        raise
