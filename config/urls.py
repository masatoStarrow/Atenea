"""
Root URL configuration for CRM API Gateway.
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── API v1 ────────────────────────────────────────────────────────
    path('api/v1/auth/', include('src.adapters.inbound.http.auth.urls')),
    path('api/v1/', include('src.adapters.inbound.http.gateway.urls')),
    path('api/v1/health/', include('src.adapters.inbound.http.health.urls')),

    # ── Documentation ─────────────────────────────────────────────────
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
