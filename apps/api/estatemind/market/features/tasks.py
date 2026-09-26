"""
Celery tasks for features module — market intelligence and analytics jobs.
"""
from celery import shared_task
from django.utils import timezone
from estatemind.market.features.services.market_analytics import run_market_intelligence_calibration
import logging

logger = logging.getLogger(__name__)


@shared_task(name='features.run_monthly_market_calibration')
def run_monthly_market_calibration():
    """
    Monthly market intelligence calibration audit.
    
    Runs on the 1st of each month at 2 AM UTC (scheduled via Celery Beat).
    Re-estimates component weights from historical DelegationMarketSnapshot outcomes,
    computes accuracy metrics, and updates the persisted calibration profile.
    
    Returns:
        dict with recalibration status, weights, and accuracy metrics
    """
    try:
        logger.info(f"[{timezone.now().isoformat()}] Starting monthly market calibration…")
        
        result = run_market_intelligence_calibration(window_months=6, persist=True)
        
        logger.info(f"[{timezone.now().isoformat()}] Market calibration completed: {result.get('status', 'unknown')}")
        logger.info(f"  • Weights: price_trend={result.get('weights', {}).get('price_trend'):.2f}, "
                   f"listing_volume={result.get('weights', {}).get('listing_volume'):.2f}, "
                   f"climate_risk={result.get('weights', {}).get('climate_risk'):.2f}, "
                   f"spatial_lag={result.get('weights', {}).get('spatial_lag'):.2f}")
        logger.info(f"  • Accuracy: directional={result.get('directional_accuracy', 0):.1%}, "
                   f"top_decile_hit_rate={result.get('top_decile_hit_rate', 0):.1%}, "
                   f"correlation={result.get('correlation_with_realized_return', 0):.3f}")
        
        return result
        
    except Exception as exc:
        logger.error(f"[{timezone.now().isoformat()}] Market calibration failed: {str(exc)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(exc),
            'timestamp': timezone.now().isoformat()
        }
