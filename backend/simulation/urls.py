from django.urls import path
from . import views

app_name = "simulation"

urlpatterns = [
    # Scenario catalogue
    path("scenarios/",                       views.scenarios_view,   name="scenarios"),
    # Start a new run
    path("start/",                           views.start_view,       name="start"),
    # Run list
    path("runs/",                            views.runs_list_view,   name="runs_list"),
    # Single run detail / delete
    path("runs/<uuid:run_id>/",              views.run_detail_view,  name="run_detail"),
    # Time-series data for a run
    path("runs/<uuid:run_id>/timeseries/",   views.timeseries_view,  name="timeseries"),
    # Summary metrics for a run
    path("runs/<uuid:run_id>/metrics/",      views.metrics_view,     name="metrics"),
    # Agent outcome breakdown for a run
    path("runs/<uuid:run_id>/agents/",       views.agents_view,      name="agents"),
    # Side-by-side comparison
    path("compare/",                         views.compare_view,     name="compare"),
    # Geographic zone price snapshot for frontend map
    path("runs/<uuid:run_id>/zones/",        views.zones_view,       name="zones"),
]
