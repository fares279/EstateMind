from django.urls import path, include
from . import views
from . import views_module7

# Legacy Module 6 endpoints
urlpatterns = [
    path('dashboard/',              views.investor_dashboard,    name='investor-dashboard'),
    path('portfolio/',              views.portfolio_list,         name='portfolio-list'),
    path('portfolio/<int:pk>/',     views.portfolio_detail,       name='portfolio-detail'),
    path('portfolio/score/',        views.portfolio_score,        name='portfolio-score'),
    path('portfolio/<int:pk>/score/', views.portfolio_score_asset, name='portfolio-score-asset'),
    path('scanner/score/',          views.scanner_score,          name='scanner-score'),
    path('scanner/history/',        views.scanner_history,        name='scanner-history'),
    path('opportunities/',          views.opportunities,          name='investor-opportunities'),
    path('risk/',                   views.risk_analysis,          name='investor-risk'),
]

# Module 7: Portfolio & Investment Intelligence
module7_patterns = [
    path('scan/',                   views_module7.scan_property,          name='investor-scan'),
    path('portfolio/',              views_module7.portfolio_analysis,     name='investor-portfolio'),
    path('portfolio/add/',          views_module7.add_portfolio_asset,    name='investor-portfolio-add'),
    path('scorers/',                views_module7.list_scorer_versions,   name='investor-scorers'),
    path('scorers/start-ab-test/',  views_module7.start_ab_test,          name='investor-scorers-start-ab-test'),
    path('scorers/promote/',        views_module7.promote_to_champion,    name='investor-scorers-promote'),
    path('scorers/rollback/',       views_module7.rollback_scorer,        name='investor-scorers-rollback'),
]

urlpatterns += module7_patterns
