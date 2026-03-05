"""
Unit tests for ValidateToken use case.
Tests valid, expired, and malformed tokens.
"""

import time

import jwt
import pytest

from src.application.use_cases.validate_token import ValidateToken
from src.domain.exceptions import TokenExpiredError, TokenInvalidError


@pytest.fixture
def validate_use_case():
    return ValidateToken(jwt_secret='test-secret-key-minimum-32-bytes!', jwt_algorithm='HS256')


def _make_token(payload, secret='test-secret-key-minimum-32-bytes!', algorithm='HS256'):
    return jwt.encode(payload, secret, algorithm=algorithm)


class TestValidateToken:
    """Tests for the ValidateToken use case."""

    def test_valid_token(self, validate_use_case):
        """Token válido → retorna claims."""
        now = int(time.time())
        token = _make_token({
            'sub': 'user-123',
            'email': 'test@crm.com',
            'role': 'admin',
            'iat': now,
            'exp': now + 3600,
        })

        claims = validate_use_case.execute(token)

        assert claims['sub'] == 'user-123'
        assert claims['email'] == 'test@crm.com'
        assert claims['role'] == 'admin'

    def test_expired_token(self, validate_use_case):
        """Token expirado → TokenExpiredError."""
        now = int(time.time())
        token = _make_token({
            'sub': 'user-123',
            'email': 'test@crm.com',
            'role': 'admin',
            'iat': now - 7200,
            'exp': now - 3600,  # Expired 1 hour ago
        })

        with pytest.raises(TokenExpiredError):
            validate_use_case.execute(token)

    def test_malformed_token(self, validate_use_case):
        """Token malformado → TokenInvalidError."""
        with pytest.raises(TokenInvalidError):
            validate_use_case.execute('not-a-valid-token')

    def test_wrong_secret_token(self, validate_use_case):
        """Token firmado con otro secret → TokenInvalidError."""
        now = int(time.time())
        token = _make_token(
            {
                'sub': 'user-123',
                'email': 'test@crm.com',
                'role': 'admin',
                'iat': now,
                'exp': now + 3600,
            },
            secret='wrong-secret-key-minimum-32-bytes!',
        )

        with pytest.raises(TokenInvalidError):
            validate_use_case.execute(token)

    def test_empty_token(self, validate_use_case):
        """Token vacío → TokenInvalidError."""
        with pytest.raises(TokenInvalidError):
            validate_use_case.execute('')
