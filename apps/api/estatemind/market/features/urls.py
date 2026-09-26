from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegionViewSet, PropertyViewSet,
    PriceTrendViewSet, ClimateRiskViewSet, MapViewSet,
    market_stats, climate_weather_by_name,
)

router = DefaultRouter()
router.register(r'map',      MapViewSet,        basename='map')
router.register(r'regions',  RegionViewSet)
router.register(r'listings', PropertyViewSet,   basename='listings')
router.register(r'trends',   PriceTrendViewSet)
router.register(r'climate',  ClimateRiskViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('stats/', market_stats, name='market-stats'),
    # Convenience: live weather by governorate name (avoids needing the DB PK)
    path('climate/weather/<str:governorate>/', climate_weather_by_name, name='climate-weather-by-name'),
]
