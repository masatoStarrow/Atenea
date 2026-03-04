"""
Health check view.
"""

import httpx
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from drf_spectacular.utils import extend_schema

from src.adapters.inbound.http.auth.serializers import SuccessResponseSerializer


class HealthView(APIView):
    """GET /api/v1/health/ — Gateway health and service connectivity."""
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary="Health check",
        description="Retorna el estado del gateway y la conectividad a los microservicios internos.",
        responses={200: SuccessResponseSerializer},
        tags=["Health"],
    )
    def get(self, request: Request) -> Response:
        services = {}

        # Check users-service
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{settings.USERS_SERVICE_URL}/health/")
                services['users-service'] = 'healthy' if r.status_code == 200 else 'unhealthy'
        except Exception:
            services['users-service'] = 'unavailable'

        # Check interactions-service
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{settings.INTERACTIONS_SERVICE_URL}/health/")
                services['interactions-service'] = 'healthy' if r.status_code == 200 else 'unhealthy'
        except Exception:
            services['interactions-service'] = 'unavailable'

        all_healthy = all(s == 'healthy' for s in services.values())

        return Response(
            {
                'success': True,
                'data': {
                    'status': 'healthy' if all_healthy else 'degraded',
                    'gateway': 'healthy',
                    'services': services,
                },
                'message': 'OK',
            },
            status=status.HTTP_200_OK,
        )
