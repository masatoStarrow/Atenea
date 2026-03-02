"""
Token entity — pure Python, no framework dependencies.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenEntity:
    """Represents a JWT access token with its claims."""
    access_token: str
    token_type: str = "Bearer"
