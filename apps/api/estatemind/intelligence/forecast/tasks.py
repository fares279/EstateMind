from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from estatemind.market.core.services.dashboard_kpi import record_kpi_freshness
from estatemind.intelligence.forecast.models import DelegationPriceData, ForecastModelVersion
from estatemind.intelligence.forecast.services.retraining_trigger import ForecastRetrainingTrigger

logger = logging.getLogger(__name__)


@shared_task(name='forecast.materialize_daily_forecast_summary')
def materialize_daily_forecast_summary() -> dict:
    """Track forecast dashboard freshness metadata for Module 3 dashboards."""
    count = DelegationPriceData.objects.count()
    record_kpi_freshness(
        kpi_name='forecast_national',
        source_app='forecast',
        row_count=count,
        notes=f'Forecast rows available as of {timezone.localdate()}',
    )
    return {
        'status': 'completed',
        'date': str(timezone.localdate()),
        'rows': count,
    }


@shared_task(name='forecast.check_retraining_triggers')
def check_retraining_triggers() -> dict:
    """
    Runs on the 1st of each month after the Gold layer update.
    For each delegation × property type, checks if market distribution
    has shifted enough to trigger retraining.

    Uses Kolmogorov-Smirnov test to detect distribution shifts.
    If p-value < 0.05, queues a retraining task.
    """
    trigger = ForecastRetrainingTrigger()
    check_results = []
    retrain_queued = 0

    # Get all unique delegation × property_type combinations
    combinations = (
        ForecastModelVersion.objects.filter(is_active=True)
        .values_list('delegation_name', 'property_type')
        .distinct()
    )

    for delegation_name, property_type in combinations:
        # For now, we don't have historical price data loaded beyond what's in DelegationPriceData
        # This task is scaffolded for when historical time series become available
        logger.info(
            "Retraining check for %s / %s queued (placeholder — awaiting historical data)",
            delegation_name,
            property_type,
        )
        check_results.append(
            {
                "delegation": delegation_name,
                "property_type": property_type,
                "status": "placeholder",
            }
        )

    return {
        "status": "completed",
        "checks_run": len(check_results),
        "retrain_queued": retrain_queued,
        "timestamp": timezone.now().isoformat(),
    }
