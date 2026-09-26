from django.urls import path

from estatemind.market.core.views import DashboardAnomaliesView, DashboardFreshnessView, MarketDashboardView

urlpatterns = [
    path('kpi-freshness/', DashboardFreshnessView.as_view(), name='kpi-freshness'),
    path('kpi-anomalies/', DashboardAnomaliesView.as_view(), name='kpi-anomalies'),
    path('market-dashboard/', MarketDashboardView.as_view(), name='market-dashboard'),
]
