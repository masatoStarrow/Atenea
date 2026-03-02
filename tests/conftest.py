"""
Shared test fixtures for all tests.
"""

import time

import jwt
import pytest
from django.conf import settings
from rest_framework.test import APIClient

from src.adapters.outbound.persistence.models.user_model import User


@pytest.fixture
def api_client():
    """DRF API test client."""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        email='admin@crm.com',
        full_name='Admin User',
        role='admin',
        password='Temporal123!',
    )


@pytest.fixture
def soporte_user(db):
    """Create a soporte user."""
    return User.objects.create_user(
        email='soporte@crm.com',
        full_name='Soporte User',
        role='soporte',
        password='Temporal123!',
    )


@pytest.fixture
def comercial_user(db):
    """Create a comercial user."""
    return User.objects.create_user(
        email='comercial@crm.com',
        full_name='Comercial User',
        role='comercial',
        password='Temporal123!',
    )


def _generate_token(user, expired=False):
    """Helper to generate a JWT token for a user."""
    now = int(time.time())
    payload = {
        'sub': str(user.id),
        'email': user.email,
        'role': user.role,
        'iat': now,
        'exp': now - 3600 if expired else now + 3600,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def admin_token(admin_user):
    """Valid JWT token for admin user."""
    return _generate_token(admin_user)


@pytest.fixture
def soporte_token(soporte_user):
    """Valid JWT token for soporte user."""
    return _generate_token(soporte_user)


@pytest.fixture
def comercial_token(comercial_user):
    """Valid JWT token for comercial user."""
    return _generate_token(comercial_user)


@pytest.fixture
def expired_token(admin_user):
    """Expired JWT token."""
    return _generate_token(admin_user, expired=True)


@pytest.fixture
def auth_admin_client(api_client, admin_token):
    """API client authenticated as admin."""
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')
    return api_client


@pytest.fixture
def auth_soporte_client(api_client, soporte_token):
    """API client authenticated as soporte."""
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {soporte_token}')
    return api_client


@pytest.fixture
def auth_comercial_client(api_client, comercial_token):
    """API client authenticated as comercial."""
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {comercial_token}')
    return api_client
