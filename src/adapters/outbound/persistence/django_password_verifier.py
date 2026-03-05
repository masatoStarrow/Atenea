"""
Django implementation of PasswordVerifierPort.
Uses Django's check_password which supports all configured hashers.
"""

from django.contrib.auth.hashers import check_password

from src.domain.ports.outbound.password_verifier_port import PasswordVerifierPort


class DjangoPasswordVerifier(PasswordVerifierPort):
    """Concrete password verifier using Django's built-in hasher system."""

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return check_password(plain_password, hashed_password)
