"""
Unit tests for LoginUser use case.
Tests pure domain logic with mocked repository.
"""

import time
from unittest.mock import MagicMock
from uuid import uuid4

import jwt
import pytest

from src.core.use_cases.login_user import LoginUser
from src.core.domain.entities.user import UserEntity
from src.core.domain.exceptions import InvalidCredentialsError


@pytest.fixture
def mock_repository():
    return MagicMock()


@pytest.fixture
def mock_password_verifier():
    verifier = MagicMock()
    verifier.verify.return_value = True
    return verifier


@pytest.fixture
def login_use_case(mock_repository, mock_password_verifier):
    return LoginUser(
        user_repository=mock_repository,
        password_verifier=mock_password_verifier,
        jwt_secret='test-secret',
        jwt_algorithm='HS256',
        jwt_expire_minutes=60,
    )


@pytest.fixture
def sample_user():
    return UserEntity(
        id=uuid4(),
        email='admin@crm.com',
        full_name='Admin User',
        role='admin',
        is_active=True,
        password_hash='hashed-password',
    )


class TestLoginUseCase:
    """Tests for the LoginUser use case."""

    def test_login_success(self, login_use_case, mock_repository, sample_user):
        """Login exitoso con credenciales válidas → retorna token."""
        mock_repository.get_by_email.return_value = sample_user

        token_entity = login_use_case.execute('admin@crm.com', 'Temporal123!')

        assert token_entity.access_token is not None
        assert token_entity.token_type == 'Bearer'

        # Decode and verify payload
        payload = jwt.decode(token_entity.access_token, 'test-secret', algorithms=['HS256'])
        assert payload['sub'] == str(sample_user.id)
        assert payload['email'] == 'admin@crm.com'
        assert payload['role'] == 'admin'
        assert 'exp' in payload
        assert 'iat' in payload

    def test_login_email_not_found(self, login_use_case, mock_repository):
        """Login con email inexistente → InvalidCredentialsError."""
        mock_repository.get_by_email.return_value = None

        with pytest.raises(InvalidCredentialsError):
            login_use_case.execute('nonexistent@crm.com', 'password')

    def test_login_wrong_password(self, login_use_case, mock_repository, mock_password_verifier, sample_user):
        """Login con contraseña incorrecta → InvalidCredentialsError."""
        mock_repository.get_by_email.return_value = sample_user
        mock_password_verifier.verify.return_value = False

        with pytest.raises(InvalidCredentialsError):
            login_use_case.execute('admin@crm.com', 'wrong-password')

    def test_login_inactive_user(self, login_use_case, mock_repository):
        """Login con usuario inactivo → InvalidCredentialsError."""
        inactive_user = UserEntity(
            id=uuid4(),
            email='inactive@crm.com',
            full_name='Inactive User',
            role='admin',
            is_active=False,
            password_hash='hashed-password',
        )
        mock_repository.get_by_email.return_value = inactive_user

        with pytest.raises(InvalidCredentialsError):
            login_use_case.execute('inactive@crm.com', 'Temporal123!')

    def test_token_expiry(self, login_use_case, mock_repository, sample_user):
        """Token has correct expiration time."""
        mock_repository.get_by_email.return_value = sample_user

        token_entity = login_use_case.execute('admin@crm.com', 'Temporal123!')
        payload = jwt.decode(token_entity.access_token, 'test-secret', algorithms=['HS256'])

        expected_exp = payload['iat'] + (60 * 60)  # 60 minutes
        assert payload['exp'] == expected_exp
