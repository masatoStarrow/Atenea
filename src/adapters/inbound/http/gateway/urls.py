"""
URL configuration for gateway proxy endpoints.
"""

from django.urls import path

from src.adapters.inbound.http.gateway.views import (
    UserProxyView,
    ClientProxyView,
    InteractionProxyView,
    InteractionByClientProxyView,
    InteractionClientSummaryProxyView,
    InteractionMetricsProxyView,
    InteractionFollowUpsProxyView,
    InteractionCloseProxyView,
    InteractionAuditProxyView,
    InteractionAttachmentProxyView,
)

urlpatterns = [
    # Users proxy
    path('users/', UserProxyView.as_view(), name='proxy-users-list'),
    path('users/<uuid:user_id>/', UserProxyView.as_view(), name='proxy-users-detail'),

    # Clients proxy
    path('clients/', ClientProxyView.as_view(), name='proxy-clients-list'),
    path('clients/<uuid:client_id>/', ClientProxyView.as_view(), name='proxy-clients-detail'),

    # Interactions proxy — specific routes BEFORE generic /{id}/
    path('interactions/metrics/', InteractionMetricsProxyView.as_view(), name='proxy-interactions-metrics'),
    path('interactions/follow-ups/<str:follow_up_type>/', InteractionFollowUpsProxyView.as_view(), name='proxy-interactions-follow-ups'),
    path('interactions/client/<uuid:client_id>/summary/', InteractionClientSummaryProxyView.as_view(), name='proxy-interactions-client-summary'),
    path('interactions/client/<uuid:client_id>/', InteractionByClientProxyView.as_view(), name='proxy-interactions-by-client'),
    path('interactions/<uuid:interaction_id>/close/', InteractionCloseProxyView.as_view(), name='proxy-interactions-close'),
    path('interactions/<uuid:interaction_id>/audit/', InteractionAuditProxyView.as_view(), name='proxy-interactions-audit'),
    path('interactions/<uuid:interaction_id>/attachments/<uuid:attachment_id>/', InteractionAttachmentProxyView.as_view(), name='proxy-interactions-attachment-detail'),
    path('interactions/<uuid:interaction_id>/attachments/', InteractionAttachmentProxyView.as_view(), name='proxy-interactions-attachments'),
    path('interactions/', InteractionProxyView.as_view(), name='proxy-interactions-list'),
    path('interactions/<uuid:interaction_id>/', InteractionProxyView.as_view(), name='proxy-interactions-detail'),
]
