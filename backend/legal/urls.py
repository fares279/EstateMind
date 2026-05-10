from django.urls import path
from .views import LegalAskView, LegalStatusView, LegalSampleQuestionsView

urlpatterns = [
    path('ask/',       LegalAskView.as_view(),            name='legal-ask'),
    path('status/',    LegalStatusView.as_view(),         name='legal-status'),
    path('questions/', LegalSampleQuestionsView.as_view(), name='legal-questions'),
]
