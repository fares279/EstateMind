from django.urls import path
from .views import (
    predict_valuation,
    valuation_history,
    get_locations,
    get_forecasts,
    get_national_forecast,
    get_forecast_delegations,
)

urlpatterns = [
    path('predict/',   predict_valuation, name='valuation-predict'),
    path('history/',   valuation_history, name='valuation-history'),
    path('locations/', get_locations,     name='valuation-locations'),

    # Price forecast endpoints (public, ML pre-computed)
    path('forecasts/',             get_forecasts,            name='valuation-forecasts'),
    path('forecasts/national/',    get_national_forecast,    name='valuation-forecasts-national'),
    path('forecasts/delegations/', get_forecast_delegations, name='valuation-forecast-delegations'),
]
