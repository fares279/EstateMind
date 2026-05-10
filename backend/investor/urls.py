from django.urls import path
from . import views

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
