"""
Unit tests for CreateUserGateway (dual-write) use case.
Verifies gateway DB + remote user-service write logic.
"""

from unittest.mock import MagicMock, AsyncMock
from uuid import UUID

import pytest

from src.application.use_cases.create_user_gateway import CreateUserGateway
from src.domain.entities.user import UserEntity
from src.domain.exceptions import EmailAlreadyExistsError, ServiceUnavailableError


# ── Helpers ──────────────────────────────────────────────────────────────

def _fake_async_runner(coro):
    """Resolve the coroutine synchronously for tests."""
    import asyncio
    return asyncio.run(coro)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_by_email.return_value = None          # email libre por defecto
    repo.create.return_value = UserEntity(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        email="test@crm.com",
        full_name="Test User",
        role="admin",
        is_active=True,
        password_hash="hashed",
    )
    return repo


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.status_code = 201
    response.json.return_value = {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "test@crm.com",
        "full_name": "Test User",
        "role": "admin",
    }
    client.forward_request = AsyncMock(return_value=response)
    return client


@pytest.fixture
def use_case(mock_repo, mock_client):
    return CreateUserGateway(
        user_repository=mock_repo,
        users_client=mock_client,
        async_runner=_fake_async_runner,
    )


# ── Tests ────────────────────────────────────────────────────────────────

class TestCreateUserGateway:
    """Tests for dual-write create user use case."""

    def test_success_creates_in_both(self, use_case, mock_repo, mock_client):
        """Happy path: user is created in gateway DB and users-service."""
        result = use_case.execute(
            email="test@crm.com",
            full_name="Test User",
            role="admin",
            password="Secure123!",
        )

        # Gateway DB was called
        mock_repo.create.assert_called_once()
        call_kwargs = mock_repo.create.call_args.kwargs
        assert call_kwargs["email"] == "test@crm.com"
        assert call_kwargs["password"] == "Secure123!"
        assert call_kwargs["role"] == "admin"
        assert isinstance(call_kwargs["user_id"], UUID)

        # Users-service was called (POST /users)
        mock_client.forward_request.assert_awaited_once()
        fwd_kwargs = mock_client.forward_request.call_args.kwargs
        assert fwd_kwargs["method"] == "POST"
        assert fwd_kwargs["path"] == "/users"
        # Verify password is NOT in the payload sent to users-service
        import json
        remote_body = json.loads(fwd_kwargs["body"])
        assert "password" not in remote_body
        assert remote_body["email"] == "test@crm.com"
        assert "id" in remote_body

        # Same UUID in both
        assert str(call_kwargs["user_id"]) == remote_body["id"]

        # Returns users-service response
        assert result["email"] == "test@crm.com"

    def test_email_already_exists_raises(self, use_case, mock_repo, mock_client):
        """If email already exists in gateway DB, raise EmailAlreadyExistsError."""
        mock_repo.get_by_email.return_value = UserEntity(
            id=UUID("00000000-0000-0000-0000-000000000099"),
            email="test@crm.com",
            full_name="Existing",
            role="admin",
            is_active=True,
            password_hash="hashed",
        )

        with pytest.raises(EmailAlreadyExistsError):
            use_case.execute(
                email="test@crm.com",
                full_name="Test User",
                role="admin",
                password="Secure123!",
            )

        # Neither DB nor remote should be called
        mock_repo.create.assert_not_called()
        mock_client.forward_request.assert_not_awaited()

    def test_rollback_on_service_unavailable(self, use_case, mock_repo, mock_client):
        """If users-service is unreachable, rollback gateway DB record."""
        mock_client.forward_request = AsyncMock(
            side_effect=ServiceUnavailableError("servicio no disponible")
        )

        with pytest.raises(ServiceUnavailableError):
            use_case.execute(
                email="test@crm.com",
                full_name="Test User",
                role="admin",
                password="Secure123!",
            )

        # Gateway record should have been created then deleted
        mock_repo.create.assert_called_once()
        mock_repo.delete_by_id.assert_called_once()
        # Same UUID passed to both create and delete
        created_id = mock_repo.create.call_args.kwargs["user_id"]
        deleted_id = mock_repo.delete_by_id.call_args[0][0]
        assert created_id == deleted_id

    def test_rollback_on_remote_4xx_error(self, use_case, mock_repo, mock_client):
        """If users-service returns 4xx/5xx, rollback gateway DB record."""
        error_response = MagicMock()
        error_response.status_code = 422
        error_response.text = "Validation error"
        mock_client.forward_request = AsyncMock(return_value=error_response)

        with pytest.raises(ServiceUnavailableError):
            use_case.execute(
                email="test@crm.com",
                full_name="Test User",
                role="admin",
                password="Secure123!",
            )

        mock_repo.create.assert_called_once()
        mock_repo.delete_by_id.assert_called_once()

    def test_password_never_sent_to_remote(self, use_case, mock_repo, mock_client):
        """Password must NEVER appear in the payload sent to users-service."""
        use_case.execute(
            email="secure@crm.com",
            full_name="Secure User",
            role="soporte",
            password="SuperSecret!",
        )

        import json
        fwd_kwargs = mock_client.forward_request.call_args.kwargs
        remote_body = json.loads(fwd_kwargs["body"])
        assert "password" not in remote_body
        assert "password_hash" not in remote_body

    def test_uuid_matches_both_stores(self, use_case, mock_repo, mock_client):
        """The same UUID must be used for both gateway DB and users-service."""
        use_case.execute(
            email="uuid@crm.com",
            full_name="UUID User",
            role="comercial",
            password="Pass1234!",
        )

        import json
        local_id = mock_repo.create.call_args.kwargs["user_id"]
        remote_body = json.loads(mock_client.forward_request.call_args.kwargs["body"])
        assert str(local_id) == remote_body["id"]
