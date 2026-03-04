"""
Django implementation of UserRepositoryPort.
Bridges the domain layer with Django ORM.
"""

from typing import Optional
from uuid import UUID

import structlog

from src.core.domain.entities.user import UserEntity
from src.core.ports.outbound.user_repository_port import UserRepositoryPort
from src.adapters.outbound.persistence.models.user_model import User

logger = structlog.get_logger(__name__)


class DjangoUserRepository(UserRepositoryPort):
    """Concrete implementation of UserRepositoryPort using Django ORM."""

    # ---- reads ----

    def get_by_email(self, email: str) -> Optional[UserEntity]:
        try:
            user = User.objects.get(email=email)
            return self._to_entity(user)
        except User.DoesNotExist:
            return None

    def get_by_id(self, user_id: str) -> Optional[UserEntity]:
        try:
            user = User.objects.get(id=user_id)
            return self._to_entity(user)
        except User.DoesNotExist:
            return None

    # ---- writes ----

    def create(self, *, user_id: UUID, email: str, full_name: str, role: str, password: str) -> UserEntity:
        user = User.objects.create_user(
            email=email,
            full_name=full_name,
            role=role,
            password=password,
            id=user_id,
        )
        logger.info("user_created_in_gateway_db", user_id=str(user_id), email=email)
        return self._to_entity(user)

    def update(self, user_id: UUID, *, full_name: str | None = None, role: str | None = None, is_active: bool | None = None) -> UserEntity:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValueError(f"User {user_id} not found in gateway DB")

        if full_name is not None:
            user.full_name = full_name
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        user.save()
        logger.info("user_updated_in_gateway_db", user_id=str(user_id))
        return self._to_entity(user)

    def deactivate(self, user_id: UUID) -> None:
        try:
            user = User.objects.get(id=user_id)
            user.is_active = False
            user.save(update_fields=["is_active"])
            logger.info("user_deactivated_in_gateway_db", user_id=str(user_id))
        except User.DoesNotExist:
            logger.warning("user_not_found_for_deactivation", user_id=str(user_id))

    def delete_by_id(self, user_id: UUID) -> None:
        """Hard delete — only used for rollback on dual-write failure."""
        deleted, _ = User.objects.filter(id=user_id).delete()
        logger.info("user_hard_deleted", user_id=str(user_id), deleted=deleted)

    # ---- helpers ----

    @staticmethod
    def _to_entity(user: User) -> UserEntity:
        return UserEntity(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            password_hash=user.password,
        )
