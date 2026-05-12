"""
Django base settings for CRM API Gateway.
Shared configuration across all environments.
"""

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Security ──────────────────────────────────────────────────────────────
SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-change-me')
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# ── Application definition ───────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'corsheaders',
    'rest_framework',
    'drf_spectacular',
    # Local
    'src.adapters.outbound.persistence',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',           # must be before CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom middleware
    'src.infrastructure.middleware.logging_middleware.LoggingMiddleware',
    'src.infrastructure.middleware.rate_limit_middleware.RateLimitMiddleware',
    'src.infrastructure.middleware.jwt_middleware.JWTMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── Database ─────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='crm_gateway_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='db'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# ── Auth ─────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'persistence.User'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internationalization ─────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ── Static files ─────────────────────────────────────────────────────────
STATIC_URL = 'static/'

# ── Default primary key field type ───────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Django REST Framework ────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'src.infrastructure.middleware.jwt_authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'src.adapters.inbound.http.exception_handler.custom_exception_handler',
}

# ── drf-spectacular ──────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'CRM API Gateway',
    'DESCRIPTION': 'Punto de entrada único del CRM. Autenticación JWT, autorización por roles y routing a microservicios. Los endpoints de usuarios implementan dual-write: crean el registro en la DB local (con contraseña) y en el users-service (sin contraseña), compartiendo el mismo UUID.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [{'BearerAuth': []}],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
                'description': 'Ingresá el JWT token obtenido en /api/v1/auth/login',
            },
        },
    },
}

# ── JWT ──────────────────────────────────────────────────────────────────
JWT_SECRET_KEY = config('JWT_SECRET_KEY', default='super-secret-jwt-key-min-32-bytes!')
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = config('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', default=60, cast=int)
JWT_ALGORITHM = config('JWT_ALGORITHM', default='HS256')

# ── Microservices URLs ───────────────────────────────────────────────────
USERS_SERVICE_URL = config('USERS_SERVICE_URL', default='http://users-service:8001/api/v1')
INTERACTIONS_SERVICE_URL = config('INTERACTIONS_SERVICE_URL', default='http://interactions-service:8002')

# ── Rate Limiting ────────────────────────────────────────────────────────
RATE_LIMIT_LOGIN = config('RATE_LIMIT_LOGIN', default='5/minute')
RATE_LIMIT_API = config('RATE_LIMIT_API', default='100/minute')

# ── CORS ─────────────────────────────────────────────────────────────────
# Origins that are allowed to make cross-site HTTP requests.
# Override CORS_ALLOWED_ORIGINS in local.py / production settings.
CORS_ALLOWED_ORIGINS: list[str] = config(
    'CORS_ALLOWED_ORIGINS',
    default='',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()],
)

# Allow cookies / Authorization header to be sent cross-origin
CORS_ALLOW_CREDENTIALS = True

# Headers the frontend is allowed to send
CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'origin',
    'x-csrftoken',
    'x-requested-with',
]
