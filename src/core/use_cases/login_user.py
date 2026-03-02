"""
Login User use case — orchestrates login flow.
Pure domain logic, no framework imports.
"""

import time

import jwt

from src.core.domain.entities.token import TokenEntity
from src.core.domain.entities.user import UserEntity
from src.core.domain.exceptions import InvalidCredentialsError
from src.core.ports.outbound.user_repository_port import UserRepositoryPort
from src.core.ports.outbound.password_verifier_port import PasswordVerifierPort


class LoginUser:
    """
    Use case: authenticate user with email + password, return JWT token.
    Dependencies injected via constructor.
    """

    def __init__(
        self,
        user_repository: UserRepositoryPort,
        password_verifier: PasswordVerifierPort,
        jwt_secret: str,
        jwt_algorithm: str,
        jwt_expire_minutes: int,
    ):
        self._user_repository = user_repository
        self._password_verifier = password_verifier
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._jwt_expire_minutes = jwt_expire_minutes

    def execute(self, email: str, password: str) -> TokenEntity:
        """
        1. Look up user by email
        2. Verify password
        3. Issue JWT token
        """
        user: UserEntity | None = self._user_repository.get_by_email(email)

        if user is None:
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InvalidCredentialsError()

        if not self._password_verifier.verify(password, user.password_hash):
            raise InvalidCredentialsError()

        token = self._generate_token(user)
        return TokenEntity(access_token=token)

    def _generate_token(self, user: UserEntity) -> str:
        """Generate a JWT token with user claims."""
        now = int(time.time())
        payload = {
            'sub': str(user.id),
            'email': user.email,
            'role': user.role,
            'iat': now,
            'exp': now + (self._jwt_expire_minutes * 60),
        }
        return jwt.encode(payload, self._jwt_secret, algorithm=self._jwt_algorithm)
