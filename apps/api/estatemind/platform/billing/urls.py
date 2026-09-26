from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BillingViewSet, stripe_webhook

router = DefaultRouter()
router.register(r'', BillingViewSet, basename='billing')

urlpatterns = [
    path('', include(router.urls)),
    path('webhook/stripe/', stripe_webhook, name='stripe-webhook'),
]
