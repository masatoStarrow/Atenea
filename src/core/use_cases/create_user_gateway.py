"""
Create User (Gateway) — dual-write use case.

1. Generate UUID
2. Persist in Gateway DB (with password_hash)
3. POST to users-service (same UUID, NO password)
4. On failure → rollback Gateway DB
"""

import json
import uuid as uuid_mod

import structlog

from src.core.domain.exceptions import (
    EmailAlreadyExistsError,
    ServiceUnavailableError,
)
from src.core.ports.outbound.user_repository_port import UserRepositoryPort


logger = structlog.get_logger(__name__)


class CreateUserGateway:
    """Orchestrates dual-write user creation across gateway DB and users-service."""

    def __init__(
        self,
        user_repository: UserRepositoryPort,
        users_client,          # UsersServiceClient (not typed to keep core framework-free)
        async_runner=None,     # callable(coro) → result  (injected for testability)
    ):
        self._repo = user_repository
        self._client = users_client
        self._run_async = async_runner or self._default_runner

    @staticmethod
    def _default_runner(coro):
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def execute(
        self,
        email: str,
        full_name: str,
        role: str,
        password: str,
        *,
        request_user_id: str | None = None,
        request_user_role: str | None = None,
    ) -> dict:
        """
        Synchronous dual-write.
        Returns the JSON response from users-service on success.
        Raises EmailAlreadyExistsError or ServiceUnavailableError on failure.
        """

        # 0. Check if email already exists in gateway DB
        if self._repo.get_by_email(email) is not None:
            raise EmailAlreadyExistsError()

        # 1. Generate shared UUID
        user_id = uuid_mod.uuid4()
        logger.info("dual_write_start", user_id=str(user_id), email=email)

        # 2. Save to Gateway DB (with password hash)
        self._repo.create(
            user_id=user_id,
            email=email,
            full_name=full_name,
            role=role,
            password=password,
        )

        # 3. POST to users-service (same UUID, NO password)
        payload = json.dumps({
            "id": str(user_id),
            "email": email,
            "full_name": full_name,
            "role": role,
        }).encode()

        try:
            response = self._run_async(
                self._client.forward_request(
                    method="POST",
                    path="/users",
                    body=payload,
                    user_id=request_user_id,
                    user_role=request_user_role,
                )
            )
        except ServiceUnavailableError:
            # Rollback gateway DB
            logger.error("dual_write_rollback_service_unavailable", user_id=str(user_id))
            self._repo.delete_by_id(user_id)
            raise

        if response.status_code >= 400:
            # Rollback gateway DB
            logger.error(
                "dual_write_rollback_remote_error",
                user_id=str(user_id),
                status=response.status_code,
                body=response.text,
            )
            self._repo.delete_by_id(user_id)
            raise ServiceUnavailableError(
                message=f"El servicio de usuarios respondió con error: {response.status_code}"
            )

        logger.info("dual_write_success", user_id=str(user_id))
        return response.json()
