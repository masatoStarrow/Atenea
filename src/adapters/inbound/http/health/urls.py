"""
URL configuration for health check endpoint.
"""

from django.urls import path

from src.adapters.inbound.http.health.views import HealthView

urlpatterns = [
    path('', HealthView.as_view(), name='health'),
]
