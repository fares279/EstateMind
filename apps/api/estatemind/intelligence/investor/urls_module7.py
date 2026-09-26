"""
Module 7: Portfolio & Investment Intelligence API URLs
"""

from django.urls import path
from . import views_module7

app_name = 'investor_api_v2'

urlpatterns = [
    # Scanner endpoints
    path('scan/', views_module7.scan_property, name='scan-property'),

    # Portfolio endpoints
    path('portfolio/add/', views_module7.add_portfolio_asset, name='add-portfolio-asset'),
    path('portfolio/analysis/', views_module7.portfolio_analysis, name='portfolio-analysis'),

    # Model registry endpoints
    path('scorers/', views_module7.list_scorer_versions, name='list-scorer-versions'),
    path('scorers/start-ab-test/', views_module7.start_ab_test, name='start-ab-test'),
    path('scorers/promote/', views_module7.promote_to_champion, name='promote-to-champion'),
    path('scorers/rollback/', views_module7.rollback_scorer, name='rollback-scorer'),
]
