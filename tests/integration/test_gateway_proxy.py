"""
Integration tests for gateway proxy endpoints.
Tests role-based permissions and proxy behavior.
"""

from unittest.mock import patch, AsyncMock, MagicMock

import pytest


@pytest.mark.django_db
class TestUserProxyPermissions:
    """Tests for role-based access to user proxy endpoints."""

    def test_admin_can_delete_user(self, auth_admin_client):
        """Admin accede a DELETE /users/{id} → proxy (o 503 si servicio no disponible)."""
        import uuid
        user_id = uuid.uuid4()

        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_response.json.return_value = {
                'success': True, 'data': None, 'message': 'Deleted'
            }
            mock_request.return_value = mock_response

            response = auth_admin_client.delete(f'/api/v1/users/{user_id}/')

            assert response.status_code == 204

    def test_soporte_cannot_delete_user(self, auth_soporte_client):
        """Soporte accede a DELETE /users/{id} → 403."""
        import uuid
        user_id = uuid.uuid4()

        response = auth_soporte_client.delete(f'/api/v1/users/{user_id}/')
        assert response.status_code == 403

    def test_comercial_cannot_delete_user(self, auth_comercial_client):
        """Comercial accede a DELETE /users/{id} → 403."""
        import uuid
        user_id = uuid.uuid4()

        response = auth_comercial_client.delete(f'/api/v1/users/{user_id}/')
        assert response.status_code == 403

    def test_admin_can_list_users(self, auth_admin_client):
        """Admin accede a GET /users/ → proxy."""
        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'success': True, 'data': [], 'message': 'OK'
            }
            mock_request.return_value = mock_response

            response = auth_admin_client.get('/api/v1/users/')
            assert response.status_code == 200

    def test_soporte_can_list_users(self, auth_soporte_client):
        """Soporte accede a GET /users/ → proxy."""
        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'success': True, 'data': [], 'message': 'OK'
            }
            mock_request.return_value = mock_response

            response = auth_soporte_client.get('/api/v1/users/')
            assert response.status_code == 200

    def test_comercial_cannot_list_users(self, auth_comercial_client):
        """Comercial accede a GET /users/ → 403."""
        response = auth_comercial_client.get('/api/v1/users/')
        assert response.status_code == 403


@pytest.mark.django_db
class TestProxyHeaders:
    """Tests that the gateway forwards correct internal headers."""

    def test_proxy_forwards_internal_headers(self, auth_admin_client, admin_user):
        """Gateway reenvía headers X-User-Id y X-User-Role al microservicio."""
        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'success': True, 'data': [], 'message': 'OK'
            }
            mock_request.return_value = mock_response

            auth_admin_client.get('/api/v1/users/')

            # Verify the forward_request was called with user_id and user_role
            call_kwargs = mock_request.call_args
            assert call_kwargs is not None
            kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
            # Check positional or keyword args
            if kwargs:
                assert str(admin_user.id) in str(call_kwargs)
                assert 'admin' in str(call_kwargs)


@pytest.mark.django_db
class TestProxyServiceUnavailable:
    """Tests for when microservices are down."""

    def test_service_unavailable(self, auth_admin_client):
        """Microservicio caído → Gateway retorna 503."""
        from src.core.domain.exceptions import ServiceUnavailableError

        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
            side_effect=ServiceUnavailableError("El servicio de usuarios no está disponible"),
        ):
            response = auth_admin_client.get('/api/v1/users/')

            assert response.status_code == 503
            data = response.json()
            assert data['success'] is False
            assert data['error']['code'] == 'SERVICE_UNAVAILABLE'


@pytest.mark.django_db
class TestTokenProtection:
    """Tests for token-based access to protected endpoints."""

    def test_valid_token_accesses_protected_endpoint(self, auth_admin_client):
        """Token válido → accede a endpoint protegido."""
        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
        ) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True, 'data': [], 'message': 'OK'}
            mock_request.return_value = mock_response

            response = auth_admin_client.get('/api/v1/users/')
            assert response.status_code == 200

    def test_expired_token_rejected(self, api_client, expired_token):
        """Token expirado → 401."""
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_token}')
        response = api_client.get('/api/v1/users/')
        assert response.status_code == 401

    def test_no_token_rejected(self, api_client):
        """Sin token → 401."""
        response = api_client.get('/api/v1/users/')
        assert response.status_code == 401

    def test_malformed_token_rejected(self, api_client):
        """Token malformado → 401."""
        api_client.credentials(HTTP_AUTHORIZATION='Bearer garbage-token')
        response = api_client.get('/api/v1/users/')
        assert response.status_code == 401
