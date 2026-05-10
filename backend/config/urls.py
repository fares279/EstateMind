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
    path('api/auth/', include('users.urls')),
    # More-specific prefixes MUST come before the generic 'api/' catch-all
    path('api/valuations/', include('valuation.urls')),
    path('api/forecast/',   include('forecast.urls')),
    path('api/campaign/', include('campaign.urls')),
    path('api/billing/', include('billing.urls')),
    path('api/scraper/', include('scraper.urls')),
    path('api/legal/', include('legal.urls')),
    path('api/investor/',  include('investor.urls')),
    path('api/simulate/', include('simulation.urls')),
    path('api/chatbot/', include('chatbot.urls')),
    path('api/', include('features.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
