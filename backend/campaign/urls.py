from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ParticipantViewSet, campaign_stats

router = DefaultRouter()
router.register(r'participants', ParticipantViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('stats/', campaign_stats, name='campaign-stats'),
]
