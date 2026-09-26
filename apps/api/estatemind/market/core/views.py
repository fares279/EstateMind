from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from estatemind.market.core.models import DashboardKPIAnomaly, DashboardKPIMetadata, MarketAnalyticsDaily


class DashboardFreshnessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        metadata = DashboardKPIMetadata.objects.all()
        payload = {
            m.kpi_name: {
                'status': m.freshness_status(),
                'computed_at': m.computed_at.isoformat(),
                'age_human': m.age_human(),
                'source_app': m.source_app,
                'row_count': m.row_count,
                'notes': m.notes,
            }
            for m in metadata
        }
        return Response(payload)


class DashboardAnomaliesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pending_only = request.query_params.get('pending', '1') != '0'
        queryset = DashboardKPIAnomaly.objects.all()
        if pending_only:
            queryset = queryset.filter(status=DashboardKPIAnomaly.STATUS_PENDING)

        return Response(
            [
                {
                    'id': row.id,
                    'kpi_name': row.kpi_name,
                    'flagged_value': row.flagged_value,
                    'z_score': row.z_score,
                    'rolling_mean': row.rolling_mean,
                    'rolling_std': row.rolling_std,
                    'reason': row.reason,
                    'detected_at': row.detected_at.isoformat(),
                    'status': row.status,
                }
                for row in queryset.order_by('-detected_at')
            ]
        )


class MarketDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today_analytics = (
            MarketAnalyticsDaily.objects
            .filter(anomaly_flagged=False)
            .order_by('-date')
            .first()
        )
        if not today_analytics:
            return Response({'error': 'No analytics available.'}, status=503)

        freshness = DashboardKPIMetadata.objects.filter(kpi_name='national_median_price').first()

        return Response(
            {
                'date': today_analytics.date.isoformat(),
                'national_median_price_sqm': today_analytics.national_median_price_sqm,
                'national_listing_count': today_analytics.national_listing_count,
                'national_avg_days_on_market': today_analytics.national_avg_days_on_market,
                'top_growing_delegations': today_analytics.top_growing_delegations,
                'top_yield_delegations': today_analytics.top_yield_delegations,
                'delegation_distribution': today_analytics.delegation_distribution,
                'property_type_breakdown': today_analytics.property_type_breakdown,
                'freshness': {
                    'status': freshness.freshness_status() if freshness else 'unknown',
                    'computed_at': freshness.computed_at.isoformat() if freshness else None,
                    'age_human': freshness.age_human() if freshness else 'Unknown',
                    'row_count': freshness.row_count if freshness else 0,
                    'source_app': freshness.source_app if freshness else 'core',
                },
            }
        )
