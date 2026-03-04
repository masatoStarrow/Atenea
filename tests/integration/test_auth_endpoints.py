"""
Integration tests for auth endpoints.
POST /api/v1/auth/login, POST /api/v1/auth/logout, GET /api/v1/auth/me
"""

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestLoginEndpoint:
    """Tests for POST /api/v1/auth/login."""

    def test_login_success(self, api_client, admin_user):
        """Login exitoso con credenciales válidas → retorna token."""
        response = api_client.post(
            '/api/v1/auth/login',
            {'email': 'admin@crm.com', 'password': 'Temporal123!'},
            format='json',
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'access_token' in data['data']
        assert data['data']['token_type'] == 'Bearer'

    def test_login_nonexistent_email(self, api_client):
        """Login con email inexistente → 401."""
        response = api_client.post(
            '/api/v1/auth/login',
            {'email': 'nobody@crm.com', 'password': 'Temporal123!'},
            format='json',
        )

        assert response.status_code == 401
        data = response.json()
        assert data['success'] is False
        assert data['error']['code'] == 'INVALID_CREDENTIALS'

    def test_login_wrong_password(self, api_client, admin_user):
        """Login con contraseña incorrecta → 401."""
        response = api_client.post(
            '/api/v1/auth/login',
            {'email': 'admin@crm.com', 'password': 'wrong-password'},
            format='json',
        )

        assert response.status_code == 401
        data = response.json()
        assert data['success'] is False
        assert data['error']['code'] == 'INVALID_CREDENTIALS'

    def test_login_incomplete_body(self, api_client):
        """Login con body incompleto → 422."""
        response = api_client.post(
            '/api/v1/auth/login',
            {'email': 'admin@crm.com'},
            format='json',
        )

        assert response.status_code == 422
        data = response.json()
        assert data['success'] is False
        assert data['error']['code'] == 'VALIDATION_ERROR'

    def test_login_empty_body(self, api_client):
        """Login con body vacío → 422."""
        response = api_client.post(
            '/api/v1/auth/login',
            {},
            format='json',
        )

        assert response.status_code == 422

    def test_login_rate_limit(self, admin_user):
        """Login 6+ veces seguidas → 429 (rate limit)."""
        client = APIClient()
        for i in range(5):
            client.post(
                '/api/v1/auth/login',
                {'email': 'admin@crm.com', 'password': 'wrong'},
                format='json',
            )

        response = client.post(
            '/api/v1/auth/login',
            {'email': 'admin@crm.com', 'password': 'wrong'},
            format='json',
        )

        assert response.status_code == 429
        data = response.json()
        assert data['error']['code'] == 'RATE_LIMIT_EXCEEDED'


@pytest.mark.django_db
class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_success(self, auth_admin_client):
        """Logout exitoso → 200."""
        response = auth_admin_client.post('/api/v1/auth/logout')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_logout_without_token(self, api_client):
        """Logout sin token → 401."""
        response = api_client.post('/api/v1/auth/logout')
        assert response.status_code == 401


@pytest.mark.django_db
class TestMeEndpoint:
    """Tests for GET /api/v1/auth/me."""

    def test_me_success(self, auth_admin_client, admin_user):
        """GET /me con token válido → perfil del usuario."""
        response = auth_admin_client.get('/api/v1/auth/me')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['data']['email'] == 'admin@crm.com'
        assert data['data']['role'] == 'admin'

    def test_me_without_token(self, api_client):
        """GET /me sin token → 401."""
        response = api_client.get('/api/v1/auth/me')
        assert response.status_code == 401

    def test_me_expired_token(self, api_client, expired_token):
        """GET /me con token expirado → 401."""
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_token}')
        response = api_client.get('/api/v1/auth/me')
        assert response.status_code == 401

    def test_me_malformed_token(self, api_client):
        """GET /me con token malformado → 401."""
        api_client.credentials(HTTP_AUTHORIZATION='Bearer not-a-real-token')
        response = api_client.get('/api/v1/auth/me')
        assert response.status_code == 401

    def test_me_no_bearer_prefix(self, api_client, admin_token):
        """GET /me sin prefijo Bearer → 401."""
        api_client.credentials(HTTP_AUTHORIZATION=admin_token)
        response = api_client.get('/api/v1/auth/me')
        assert response.status_code == 401
