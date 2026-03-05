"""
HTTP client for crm-interactions-service.
Uses httpx for async HTTP calls.
"""

import uuid

import httpx
from django.conf import settings

from src.domain.exceptions import ServiceUnavailableError


class InteractionsServiceClient:
    """HTTP client to proxy requests to the interactions microservice."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.INTERACTIONS_SERVICE_URL).rstrip('/')

    async def forward_request(
        self,
        method: str,
        path: str,
        headers: dict | None = None,
        body: bytes | None = None,
        query_params: dict | None = None,
        user_id: str | None = None,
        user_role: str | None = None,
    ) -> httpx.Response:
        """
        Forward an HTTP request to the interactions-service.
        Injects internal headers (X-User-Id, X-User-Role, X-Request-Id).
        """
        url = f"{self.base_url}{path}"

        internal_headers = {
            'X-Request-Id': str(uuid.uuid4()),
            'Content-Type': 'application/json',
        }
        if user_id:
            internal_headers['X-User-Id'] = user_id
        if user_role:
            internal_headers['X-User-Role'] = user_role

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=internal_headers,
                    content=body,
                    params=query_params,
                )
                return response
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
            raise ServiceUnavailableError(
                message="El servicio de interacciones no está disponible"
            )
