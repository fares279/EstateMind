from django.urls import path
from estatemind.intelligence.climate import views

urlpatterns = [
    # Delegation-level climate data
    path(
        'delegation/<str:delegation_name>/',
        views.delegation_climate_detail,
        name='climate-delegation-detail'
    ),
    
    # Point-level kriging interpolation
    path(
        'point/',
        views.climate_point_query,
        name='climate-point-query'
    ),
    
    # Heatmap GeoJSON
    path(
        'heatmap/',
        views.climate_heatmap,
        name='climate-heatmap'
    ),
    
    # National summary statistics
    path(
        'summary/',
        views.climate_summary,
        name='climate-summary'
    ),
    
    # Freshness monitoring
    path(
        'freshness/',
        views.climate_freshness_status,
        name='climate-freshness'
    ),
    
    # Admin recalibration trigger
    path(
        'recalibrate/',
        views.trigger_climate_recalibration,
        name='climate-recalibrate'
    ),
]
