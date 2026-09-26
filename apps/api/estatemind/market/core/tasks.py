from __future__ import annotations

import logging
from statistics import median

from celery import shared_task
from django.db.models import Avg, Sum
from django.utils import timezone

from estatemind.market.core.models import (
    DashboardKPIAnomaly,
    DelegationMarketSegment,
    DelegationMarketSnapshot,
    MarketAnalyticsDaily,
)
from estatemind.market.core.services.anomaly_detector import KPIAnomalyDetector
from estatemind.market.core.services.dashboard_kpi import record_kpi_freshness

logger = logging.getLogger(__name__)


def _safe_median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(median(values))


@shared_task(name='core.materialize_daily_market_analytics')
def materialize_daily_market_analytics() -> dict:
    """Build daily precomputed market analytics row consumed by dashboards."""
    today = timezone.localdate()
    latest_date = (
        DelegationMarketSnapshot.objects.order_by('-as_of_date')
        .values_list('as_of_date', flat=True)
        .first()
    )
    if not latest_date:
        return {'status': 'skipped', 'reason': 'no_snapshots'}

    snapshots = list(
        DelegationMarketSnapshot.objects
        .filter(as_of_date=latest_date)
        .select_related('delegation__region')
    )
    if not snapshots:
        return {'status': 'skipped', 'reason': 'empty_snapshot_set'}

    median_values = [float(s.median_price_per_sqm) for s in snapshots if s.median_price_per_sqm]
    national_median = _safe_median(median_values)
    national_listing_count = int(sum(s.listing_count or 0 for s in snapshots))
    dom_values = [float(s.median_days_on_market) for s in snapshots if s.median_days_on_market is not None]
    avg_days_on_market = (sum(dom_values) / len(dom_values)) if dom_values else 0.0

    # Approximate growth proxy using forecast and current median where available.
    growth_rows = []
    for s in snapshots:
        if s.forecast_6m and s.median_price_per_sqm and s.median_price_per_sqm > 0:
            trend_pct = ((float(s.forecast_6m) - float(s.median_price_per_sqm)) / float(s.median_price_per_sqm)) * 100
            growth_rows.append(
                {
                    'name': s.delegation.name,
                    'governorate': s.delegation.region.governorate,
                    'trend_pct': round(trend_pct, 2),
                }
            )
    top_growing = sorted(growth_rows, key=lambda row: row['trend_pct'], reverse=True)[:10]

    # Simple yield proxy from latest rent/sale medians.
    yield_rows = []
    for s in snapshots:
        if s.median_rent_price and s.median_sale_price and s.median_sale_price > 0:
            annual_yield = (float(s.median_rent_price) * 12.0 / float(s.median_sale_price)) * 100
            yield_rows.append(
                {
                    'name': s.delegation.name,
                    'governorate': s.delegation.region.governorate,
                    'yield_pct': round(annual_yield, 2),
                }
            )
    top_yield = sorted(yield_rows, key=lambda row: row['yield_pct'], reverse=True)[:10]

    delegation_distribution = {
        s.delegation.name: int(s.listing_count or 0)
        for s in snapshots
    }

    segment_counts = (
        DelegationMarketSegment.objects
        .filter(snapshot__as_of_date=latest_date)
        .values('property_type')
        .annotate(total=Sum('listing_count'))
        .order_by('property_type')
    )
    property_type_breakdown = {
        row['property_type']: int(row['total'] or 0)
        for row in segment_counts
    }

    detector = KPIAnomalyDetector()
    anomaly_check = detector.check('national_median_price', national_median)
    if anomaly_check['anomaly']:
        logger.error(
            'ANOMALY: national_median_price z=%s (new=%.2f, mean=%s, std=%s) quarantined',
            anomaly_check.get('z_score'),
            national_median,
            anomaly_check.get('mean'),
            anomaly_check.get('std'),
        )
        DashboardKPIAnomaly.objects.create(
            kpi_name='national_median_price',
            flagged_value=national_median,
            z_score=anomaly_check.get('z_score'),
            rolling_mean=anomaly_check.get('mean'),
            rolling_std=anomaly_check.get('std'),
            reason=anomaly_check.get('reason', 'z_score_exceeded'),
            status=DashboardKPIAnomaly.STATUS_PENDING,
        )

    MarketAnalyticsDaily.objects.update_or_create(
        date=today,
        defaults={
            'national_median_price_sqm': national_median,
            'national_listing_count': national_listing_count,
            'national_avg_days_on_market': round(avg_days_on_market, 2),
            'top_growing_delegations': top_growing,
            'top_yield_delegations': top_yield,
            'delegation_distribution': delegation_distribution,
            'property_type_breakdown': property_type_breakdown,
            'anomaly_checked': True,
            'anomaly_flagged': bool(anomaly_check['anomaly']),
        },
    )

    if not anomaly_check['anomaly']:
        record_kpi_freshness(
            kpi_name='national_median_price',
            source_app='core',
            row_count=len(median_values),
            notes=f'Computed from {len(snapshots)} delegation snapshots @ {latest_date}',
        )

    record_kpi_freshness(
        kpi_name='top_growing_delegations',
        source_app='core',
        row_count=len(top_growing),
        notes=f'Computed top growing delegations @ {latest_date}',
    )
    record_kpi_freshness(
        kpi_name='top_yield_delegations',
        source_app='core',
        row_count=len(top_yield),
        notes=f'Computed top yield delegations @ {latest_date}',
    )
    record_kpi_freshness(
        kpi_name='national_listing_volume',
        source_app='core',
        row_count=national_listing_count,
        notes=f'Latest snapshot date {latest_date}',
    )

    return {
        'status': 'completed',
        'date': str(today),
        'latest_snapshot_date': str(latest_date),
        'anomaly_flagged': bool(anomaly_check['anomaly']),
        'national_median_price_sqm': round(national_median, 2),
        'national_listing_count': national_listing_count,
    }
