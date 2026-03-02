"""
URL configuration for gateway proxy endpoints.
"""

from django.urls import path

from src.adapters.inbound.http.gateway.views import (
    UserProxyView,
    ClientProxyView,
    InteractionProxyView,
    InteractionByClientProxyView,
)

urlpatterns = [
    # Users proxy
    path('users/', UserProxyView.as_view(), name='proxy-users-list'),
    path('users/<uuid:user_id>/', UserProxyView.as_view(), name='proxy-users-detail'),

    # Clients proxy
    path('clients/', ClientProxyView.as_view(), name='proxy-clients-list'),
    path('clients/<uuid:client_id>/', ClientProxyView.as_view(), name='proxy-clients-detail'),

    # Interactions proxy
    path('interactions/', InteractionProxyView.as_view(), name='proxy-interactions-list'),
    path('interactions/<uuid:interaction_id>/', InteractionProxyView.as_view(), name='proxy-interactions-detail'),
    path('interactions/client/<uuid:client_id>/', InteractionByClientProxyView.as_view(), name='proxy-interactions-by-client'),
]
