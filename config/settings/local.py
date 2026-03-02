"""
Local development settings.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

# ── CORS (development) ───────────────────────────────────────────────────
# Allow requests from the Vite dev server (default port 5173).
# Add any other local origins you need here.
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]

# ── Logging (consola) ────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
