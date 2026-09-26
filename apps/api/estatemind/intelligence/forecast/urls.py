from django.urls import path
from .views import (
    get_forecasts,
    get_national_forecast,
    get_forecast_delegations,
    get_market_data,
)

urlpatterns = [
    path('',             get_forecasts,            name='forecast-list'),
    path('national/',    get_national_forecast,    name='forecast-national'),
    path('delegations/', get_forecast_delegations, name='forecast-delegations'),
    path('market/',      get_market_data,          name='forecast-market'),
]
