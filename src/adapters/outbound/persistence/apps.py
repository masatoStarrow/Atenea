"""
Django app configuration for the persistence adapter.
"""

from django.apps import AppConfig


class PersistenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'src.adapters.outbound.persistence'
    label = 'persistence'
    verbose_name = 'Persistence Adapter'
