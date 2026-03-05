"""
Dependency Injection container.
Assembles use cases with their real dependencies.
"""

from django.conf import settings

from src.application.use_cases.login_user import LoginUser
from src.application.use_cases.validate_token import ValidateToken
from src.adapters.outbound.persistence.django_user_repository import DjangoUserRepository
from src.adapters.outbound.persistence.django_password_verifier import DjangoPasswordVerifier


def get_user_repository() -> DjangoUserRepository:
    """Get the concrete user repository implementation."""
    return DjangoUserRepository()


def get_password_verifier() -> DjangoPasswordVerifier:
    """Get the concrete password verifier implementation."""
    return DjangoPasswordVerifier()


def get_login_use_case() -> LoginUser:
    """Assemble the LoginUser use case with real dependencies."""
    return LoginUser(
        user_repository=get_user_repository(),
        password_verifier=get_password_verifier(),
        jwt_secret=settings.JWT_SECRET_KEY,
        jwt_algorithm=settings.JWT_ALGORITHM,
        jwt_expire_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    )


def get_validate_token_use_case() -> ValidateToken:
    """Assemble the ValidateToken use case."""
    return ValidateToken(
        jwt_secret=settings.JWT_SECRET_KEY,
        jwt_algorithm=settings.JWT_ALGORITHM,
    )
