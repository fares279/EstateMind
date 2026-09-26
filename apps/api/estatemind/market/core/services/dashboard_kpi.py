from __future__ import annotations

from django.utils import timezone

from estatemind.market.core.models import DashboardKPIMetadata


def record_kpi_freshness(kpi_name: str, source_app: str, row_count: int = 0, notes: str = '') -> DashboardKPIMetadata:
    """Update freshness metadata for a KPI after successful computation."""
    metadata, _ = DashboardKPIMetadata.objects.update_or_create(
        kpi_name=kpi_name,
        defaults={
            'computed_at': timezone.now(),
            'source_app': source_app,
            'row_count': row_count,
            'notes': notes,
        },
    )
    return metadata
