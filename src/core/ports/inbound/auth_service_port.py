"""
Auth service port — inbound port (ABC).
Defines the contract for the authentication use case.
"""

from abc import ABC, abstractmethod

from src.core.domain.entities.token import TokenEntity


class AuthServicePort(ABC):
    """Port for authentication operations."""

    @abstractmethod
    def login(self, email: str, password: str) -> TokenEntity:
        """Authenticate a user and return a TokenEntity."""
        ...

    @abstractmethod
    def validate_token(self, token: str) -> dict:
        """Validate a JWT token and return its claims."""
        ...
