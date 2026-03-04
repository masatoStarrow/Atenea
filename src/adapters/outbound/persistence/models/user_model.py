"""
Django ORM User model for the CRM API Gateway.
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom manager for the User model."""

    def create_user(self, email, full_name, role, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, role='admin', password=None, **extra_fields):
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, full_name, role, password, **extra_fields)


class User(AbstractBaseUser):
    """
    Gateway user model for authentication.
    Uses UUID as primary key and email as the unique identifier.
    """

    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('soporte', 'Soporte'),
        ('comercial', 'Comercial'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'role']

    class Meta:
        app_label = 'persistence'
        db_table = 'users'

    def __str__(self):
        return f"{self.email} ({self.role})"
