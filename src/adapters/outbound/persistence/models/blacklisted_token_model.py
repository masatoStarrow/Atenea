"""
Blacklisted Token model for logout functionality.
"""

import uuid

from django.db import models


class BlacklistedToken(models.Model):
    """
    Stores invalidated JWT tokens (logout).
    In production, migrate this to Redis for better performance.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.TextField(unique=True)
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        app_label = 'persistence'
        db_table = 'blacklisted_tokens'

    def __str__(self):
        return f"Blacklisted token {self.id}"
