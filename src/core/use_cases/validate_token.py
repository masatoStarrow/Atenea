"""
Validate Token use case — decodes and validates JWT.
Pure domain logic, no framework imports.
"""

import jwt

from src.core.domain.exceptions import TokenExpiredError, TokenInvalidError


class ValidateToken:
    """
    Use case: decode a JWT token and return its claims.
    Dependencies injected via constructor.
    """

    def __init__(self, jwt_secret: str, jwt_algorithm: str):
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm

    def execute(self, token: str) -> dict:
        """
        Decode and validate a JWT token.
        Returns the claims dict if valid.
        Raises TokenExpiredError or TokenInvalidError on failure.
        """
        try:
            payload = jwt.decode(
                token,
                self._jwt_secret,
                algorithms=[self._jwt_algorithm],
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError()
        except jwt.InvalidTokenError:
            raise TokenInvalidError()
