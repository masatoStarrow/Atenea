"""
User repository port — outbound port (ABC).
Defines the contract for user data access.
"""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.entities.user import UserEntity


class UserRepositoryPort(ABC):
    """Port for user persistence operations."""

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[UserEntity]:
        """Retrieve a user by email. Returns None if not found."""
        ...

    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[UserEntity]:
        """Retrieve a user by ID. Returns None if not found."""
        ...

    @abstractmethod
    def create(self, *, user_id: UUID, email: str, full_name: str, role: str, password: str) -> UserEntity:
        """Create a new user with hashed password."""
        ...

    @abstractmethod
    def update(self, user_id: UUID, *, full_name: str | None = None, role: str | None = None, is_active: bool | None = None) -> UserEntity:
        """Update an existing user."""
        ...

    @abstractmethod
    def deactivate(self, user_id: UUID) -> None:
        """Soft delete — set is_active=False."""
        ...

    @abstractmethod
    def delete_by_id(self, user_id: UUID) -> None:
        """Hard delete a user (for rollback)."""
        ...
