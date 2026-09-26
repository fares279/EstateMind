from django.urls import path
from .views import (
    predict_valuation,
    valuation_history,
    valuation_model_registry,
    valuation_calibration_report,
    valuation_drift_report,
    valuation_audit_log,
    promote_model_version,
    get_locations,
    get_forecasts,
    get_national_forecast,
    get_forecast_delegations,
)

urlpatterns = [
    path('predict/',   predict_valuation, name='valuation-predict'),
    path('history/',   valuation_history, name='valuation-history'),
    path('locations/', get_locations,     name='valuation-locations'),
    path('registry/', valuation_model_registry, name='valuation-registry'),
    path('calibration/', valuation_calibration_report, name='valuation-calibration'),
    path('drift/', valuation_drift_report, name='valuation-drift'),
    path('audit/', valuation_audit_log, name='valuation-audit'),
    path('registry/<int:version_id>/promote/', promote_model_version, name='valuation-promote-model'),

    # Price forecast endpoints (public, ML pre-computed)
    path('forecasts/',             get_forecasts,            name='valuation-forecasts'),
    path('forecasts/national/',    get_national_forecast,    name='valuation-forecasts-national'),
    path('forecasts/delegations/', get_forecast_delegations, name='valuation-forecast-delegations'),
]
