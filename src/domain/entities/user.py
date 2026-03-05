"""
User entity — pure Python, no framework dependencies.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UserEntity:
    """Represents a user in the domain layer."""
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    password_hash: str
