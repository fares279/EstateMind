from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

import config.admin_site  # noqa: F401 — applies custom get_app_list grouping

# ── Admin site branding ───────────────────────────────────────────────────────
admin.site.site_header  = 'EstateMind Administration'
admin.site.site_title   = 'EstateMind Admin'
admin.site.index_title  = 'Platform Control Panel'


def healthz(request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz', healthz, name='healthz'),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema')),
    path('api/auth/', include('estatemind.platform.users.urls')),
    # More-specific prefixes MUST come before the generic 'api/' catch-all
    path('api/climate/', include('estatemind.intelligence.climate.urls')),
    path('api/valuations/', include('estatemind.intelligence.valuation.urls')),
    path('api/forecast/',   include('estatemind.intelligence.forecast.urls')),
    path('api/campaign/', include('estatemind.platform.campaign.urls')),
    path('api/billing/', include('estatemind.platform.billing.urls')),
    path('api/scraper/', include('estatemind.market.scraper.urls')),
    path('api/legal/', include('estatemind.assistants.legal.urls')),
    path('api/investor/',  include('estatemind.intelligence.investor.urls')),
    path('api/simulate/', include('estatemind.intelligence.simulation.urls')),
    path('api/chatbot/', include('estatemind.assistants.chatbot.urls')),
    path('api/core/', include('estatemind.market.core.urls')),
    path('api/', include('estatemind.market.features.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


def server_error(request):
    """Unhandled errors outside DRF (DEBUG=False): JSON with a plain message, not an HTML page."""
    from estatemind.platform.errors import GENERIC_MESSAGE
    return JsonResponse({'error': GENERIC_MESSAGE}, status=500)


handler500 = server_error
