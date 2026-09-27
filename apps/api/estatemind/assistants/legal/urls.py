from django.urls import path

from .views import (
    LegalAskView,
    LegalFeedbackView,
    LegalSampleQuestionsView,
    LegalSessionView,
    LegalStatusView,
)

urlpatterns = [
    path('ask/',       LegalAskView.as_view(),             name='legal-ask'),
    path('feedback/',  LegalFeedbackView.as_view(),        name='legal-feedback'),
    path('session/',   LegalSessionView.as_view(),         name='legal-session'),
    path('status/',    LegalStatusView.as_view(),          name='legal-status'),
    path('questions/', LegalSampleQuestionsView.as_view(), name='legal-questions'),
]
