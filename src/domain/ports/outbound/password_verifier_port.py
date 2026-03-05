"""
Password verifier port — outbound port (ABC).
Defines the contract for password verification.
"""

from abc import ABC, abstractmethod


class PasswordVerifierPort(ABC):
    """Port for password verification operations."""

    @abstractmethod
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password."""
        ...
