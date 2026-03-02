"""
Integration tests for dual-write user creation.
Verifies that POST /api/v1/users/ creates in gateway DB + proxies to users-service.
"""

from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from src.adapters.outbound.persistence.models.user_model import User


@pytest.mark.django_db
class TestDualWriteCreateUser:
    """Integration tests for POST /api/v1/users/ dual-write."""

    def test_create_user_stores_in_gateway_db(self, auth_admin_client):
        """POST creates user in gateway DB with password, then proxies to remote."""
        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
        ) as mock_fwd:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "email": "nuevo@crm.com",
                "full_name": "Nuevo User",
                "role": "soporte",
            }
            mock_fwd.return_value = mock_response

            response = auth_admin_client.post(
                '/api/v1/users/',
                data={
                    "email": "nuevo@crm.com",
                    "full_name": "Nuevo User",
                    "role": "soporte",
                    "password": "Temporal123!",
                },
                format='json',
            )

            assert response.status_code == 201

            # Verify user exists in gateway DB
            gw_user = User.objects.get(email="nuevo@crm.com")
            assert gw_user.role == "soporte"
            assert gw_user.check_password("Temporal123!")

            # Verify remote was called
            mock_fwd.assert_awaited_once()
            call_kw = mock_fwd.call_args.kwargs
            assert call_kw["method"] == "POST"
            assert call_kw["path"] == "/users"

            # Password must NOT be in remote payload
            import json
            body = json.loads(call_kw["body"])
            assert "password" not in body
            assert "password_hash" not in body

    def test_create_user_rollback_on_remote_failure(self, auth_admin_client):
        """If remote returns error, gateway DB record is deleted (rollback)."""
        from src.core.domain.exceptions import ServiceUnavailableError

        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
            side_effect=ServiceUnavailableError("servicio caído"),
        ):
            response = auth_admin_client.post(
                '/api/v1/users/',
                data={
                    "email": "rollback@crm.com",
                    "full_name": "Rollback User",
                    "role": "admin",
                    "password": "Temporal123!",
                },
                format='json',
            )

            assert response.status_code == 503
            # User should NOT remain in gateway DB
            assert not User.objects.filter(email="rollback@crm.com").exists()

    def test_create_user_duplicate_email_409(self, auth_admin_client, admin_user):
        """Creating a user with an existing email returns 409."""
        response = auth_admin_client.post(
            '/api/v1/users/',
            data={
                "email": admin_user.email,  # already exists
                "full_name": "Duplicate",
                "role": "soporte",
                "password": "Temporal123!",
            },
            format='json',
        )

        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "EMAIL_ALREADY_EXISTS"

    def test_create_user_missing_password_400(self, auth_admin_client):
        """POST without password field returns 400 validation error."""
        response = auth_admin_client.post(
            '/api/v1/users/',
            data={
                "email": "nopass@crm.com",
                "full_name": "No Pass",
                "role": "admin",
            },
            format='json',
        )

        assert response.status_code == 400

    def test_create_user_uuid_matches(self, auth_admin_client):
        """UUID in gateway DB must match UUID sent to users-service."""
        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
        ) as mock_fwd:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "placeholder"}
            mock_fwd.return_value = mock_response

            auth_admin_client.post(
                '/api/v1/users/',
                data={
                    "email": "uuidcheck@crm.com",
                    "full_name": "UUID Check",
                    "role": "comercial",
                    "password": "Temporal123!",
                },
                format='json',
            )

            # Get UUID from gateway DB
            gw_user = User.objects.get(email="uuidcheck@crm.com")

            # Get UUID sent to remote
            import json
            body = json.loads(mock_fwd.call_args.kwargs["body"])
            assert str(gw_user.id) == body["id"]


@pytest.mark.django_db
class TestDualWriteUpdateUser:
    """Integration tests for PUT /api/v1/users/{id} dual-write."""

    def test_update_user_updates_gateway_db(self, auth_admin_client, admin_user):
        """PUT updates user in gateway DB and proxies to remote."""
        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
        ) as mock_fwd:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": str(admin_user.id), "role": "soporte"}
            mock_fwd.return_value = mock_response

            response = auth_admin_client.put(
                f'/api/v1/users/{admin_user.id}/',
                data={"role": "soporte"},
                format='json',
            )

            assert response.status_code == 200

            # Verify gateway DB was updated
            admin_user.refresh_from_db()
            assert admin_user.role == "soporte"

            # Verify remote was called
            mock_fwd.assert_awaited_once()


@pytest.mark.django_db
class TestDualWriteDeleteUser:
    """Integration tests for DELETE /api/v1/users/{id} dual-write."""

    def test_delete_user_deactivates_in_gateway(self, auth_admin_client):
        """DELETE deactivates user in gateway DB and proxies to remote."""
        # Create a separate user to delete
        target = User.objects.create_user(
            email="todelete@crm.com",
            full_name="Delete Me",
            role="soporte",
            password="Temporal123!",
        )

        with patch(
            'src.adapters.outbound.http_client.users_client.UsersServiceClient.forward_request',
            new_callable=AsyncMock,
        ) as mock_fwd:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_response.json.return_value = {"success": True}
            mock_fwd.return_value = mock_response

            response = auth_admin_client.delete(f'/api/v1/users/{target.id}/')
            assert response.status_code == 204

            # User should be deactivated in gateway DB
            target.refresh_from_db()
            assert target.is_active is False

            # Remote was called with DELETE
            mock_fwd.assert_awaited_once()
            assert mock_fwd.call_args.kwargs["method"] == "DELETE"
