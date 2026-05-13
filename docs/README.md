# CRM API Gateway — Documentación Completa

## Índice

1. [Descripción General](#1-descripción-general)
2. [Arquitectura del Proyecto](#2-arquitectura-del-proyecto)
3. [Guía de Instalación y Ejecución](#3-guía-de-instalación-y-ejecución)
4. [Comandos — Qué hace cada uno y cuándo usarlo](#4-comandos--qué-hace-cada-uno-y-cuándo-usarlo)
5. [Endpoints de la API](#5-endpoints-de-la-api)
6. [Documentación Swagger (OpenAPI)](#6-documentación-swagger-openapi)
7. [Autenticación y JWT](#7-autenticación-y-jwt)
8. [Sistema de Permisos por Rol](#8-sistema-de-permisos-por-rol)
9. [Variables de Entorno](#9-variables-de-entorno)
10. [Tests](#10-tests)
11. [Estructura de Archivos Explicada](#11-estructura-de-archivos-explicada)
12. [Preguntas Frecuentes (FAQ)](#12-preguntas-frecuentes-faq)

---

## 1. Descripción General

El **CRM API Gateway** es el punto de entrada único para todos los clientes (frontend web, mobile) del CRM empresarial. Es responsable de:

- **Autenticar usuarios** con email y contraseña, emitiendo tokens JWT.
- **Validar permisos por rol** (admin, soporte, comercial) en cada request.
- **Aplicar rate limiting** para proteger contra abuso.
- **Centralizar logs** estructurados (JSON) para observabilidad.
- **Hacer proxy/routing** hacia los microservicios internos (`users-service`, `interactions-service`).

### Stack Tecnológico

| Componente | Tecnología | Versión |
|---|---|---|
| Framework | Django | 6.0.2 |
| API REST | Django REST Framework | 3.16.1 |
| Lenguaje | Python | 3.13+ |
| Base de datos | PostgreSQL (Docker) | 15 |
| Autenticación | PyJWT | 2.11.0 |
| HTTP Client (async) | httpx | 0.28.1 |
| CORS | django-cors-headers | 4.7.0 |
| Rate Limiting | Middleware custom | — |
| Logging | structlog | 25.5.0 |
| Documentación API | drf-spectacular | 0.29.0 |
| Testing | pytest + pytest-django | 9.0.2 / 4.12.0 |
| Containerización | Docker + docker-compose | — |

---

## 2. Arquitectura del Proyecto

Se usa **Clean Architecture** siguiendo los principios del [**scaffold de Bancolombia**](https://bancolombia.github.io/scaffold-clean-architecture/docs/intro), adaptados de Java/Gradle a Python/Django. La idea central: el dominio (lógica de negocio) no depende de ningún framework. Django, DRF, httpx son detalles de implementación que viven en los adaptadores.

### ¿Por qué el scaffold de Bancolombia?

1. **Regla de dependencia estricta:** las capas internas (dominio, aplicación) no importan Django ni DRF. Si mañana cambiamos Django por Flask, solo se reescriben los adaptadores.
2. **Testabilidad:** los casos de uso (`login_user`, `validate_token`) se prueban con mocks puros — sin BD ni servidor HTTP.
3. **Separación de responsabilidades:** las vistas DRF solo traducen HTTP ↔ caso de uso. No contienen lógica de negocio.
4. **Escalabilidad del equipo:** diferentes personas pueden trabajar en middleware, vistas proxy y casos de uso sin conflictos.

### Mapeo Bancolombia → Python/Django

| Capa Bancolombia | Módulo Bancolombia | Nuestro equivalente | Qué contiene |
|---|---|---|---|
| **Domain** | `model` | `src/domain/` | Entidades (Token, User), puertos (ABCs), excepciones |
| **Domain** | `usecase` | `src/application/` | Casos de uso: login, validate_token, create_user_gateway |
| **Infrastructure** | `entry-points` | `src/adapters/inbound/` | Vistas DRF (auth, gateway, health), serializers |
| **Infrastructure** | `driven-adapters` | `src/adapters/outbound/` | Repos Django ORM, httpx clients, management commands |
| **Infrastructure** | `helpers` | `src/infrastructure/` | Middleware, permisos, DI, logging |
| **Application** | `app-service` | `manage.py` + `config/` | Entry point Django, settings por ambiente |

```
┌──────────────────────────────────────────────────────────┐
│                    CLIENTE (Web/Mobile)                   │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼───────────────────────────────────┐
│              MIDDLEWARE (Infraestructura)                 │
│  LoggingMiddleware → RateLimitMiddleware → JWTMiddleware  │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│             ADAPTADORES INBOUND (DRF Views)              │
│  AuthViews (/auth/login, /logout, /me)                   │
│  GatewayViews (proxy → microservicios)                   │
│  HealthView (/health/)                                   │
└──────────┬───────────────────────────────┬───────────────┘
           │                               │
┌──────────▼──────────┐     ┌──────────────▼───────────────┐
│  DOMINIO + APLICACIÓN│     │   ADAPTADORES OUTBOUND       │
│  Entities (Token,   │     │  DjangoUserRepository        │
│    User)            │     │  DjangoPasswordVerifier       │
│  Use Cases (Login,  │     │  UsersServiceClient (httpx)   │
│    ValidateToken)   │     │  InteractionsServiceClient    │
│  Ports (ABCs)       │     │                               │
│  Exceptions         │     │  PostgreSQL (Django ORM)      │
└─────────────────────┘     └───────────────────────────────┘
```

### Las 4 capas

| Capa | Carpeta | Qué contiene | Importa frameworks? |
|---|---|---|---|
| **Dominio** | `src/domain/` | Entidades, excepciones, puertos (ABCs) | ❌ Solo Python puro |
| **Aplicación** | `src/application/` | Casos de uso (orquestan dominio + ports) | ❌ Solo Python puro + PyJWT |
| **Adaptadores** | `src/adapters/` | Views DRF, ORM repositories, HTTP clients | ✅ Django, DRF, httpx |
| **Infraestructura** | `src/infrastructure/` | Middleware, permisos, logging, inyección de dependencias | ✅ Django, structlog |

---

## 3. Guía de Instalación y Ejecución

### Requisitos previos
- Docker y Docker Compose instalados
- Git

### Paso a paso (primera vez)

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd Atenea

# 2. Copiar variables de entorno
cp .env.example .env

# 3. Crear la red compartida (una sola vez)
sudo docker network create crm_network

# 4. Construir y levantar Atenea
sudo docker-compose up --build -d

# 5. Aplicar migraciones (crear tablas en la BD)
sudo docker-compose exec gateway python manage.py migrate

# 6. Levantar Artemisa (ver su README) y aplicar sus migraciones

# 7. Crear usuarios iniciales (dual-write: se crean en Gateway DB + Artemisa con el mismo UUID)
# ⚠️  Artemisa DEBE estar corriendo antes de ejecutar este comando
sudo docker-compose exec gateway python manage.py seed_users
```

> **Atajo:** usá `./startup.sh` desde la raiz de Atenea para hacer todos los pasos anteriores
> (incluyendo Artemisa) con un solo comando.

### Ejecuciones posteriores (ya todo está creado)

```bash
# Solo levantar los servicios (sin reconstruir)
sudo docker-compose up
```

> **¿Cuándo necesito `--build`?** Solo cuando cambies el `Dockerfile`, `requirements.txt`, o agregar nuevas dependencias. Si solo cambiás código Python, no hace falta `--build` porque el volumen (`.:/app`) sincroniza los archivos automáticamente.

### Detener los servicios

```bash
# Detener (mantiene datos de la BD)
sudo docker-compose down

# Detener y BORRAR TODO (incluyendo BD)
sudo docker-compose down -v
```

---

## 4. Comandos — Qué hace cada uno y cuándo usarlo

### Comandos Docker

| Comando | Qué hace | ¿Cuándo ejecutarlo? |
|---|---|---|
| `sudo docker-compose up --build` | Construye la imagen Docker e inicia gateway + postgres | **Primera vez** o cuando cambies Dockerfile/requirements.txt |
| `sudo docker-compose up` | Inicia los servicios sin reconstruir la imagen | **Cada vez** que quieras trabajar (ejecuciones normales) |
| `sudo docker-compose down` | Detiene los contenedores, mantiene los datos de BD | Cuando termines de trabajar |
| `sudo docker-compose down -v` | Detiene contenedores Y borra la base de datos | Si querés resetear todo desde cero |
| `sudo docker-compose logs -f gateway` | Ver logs del gateway en tiempo real | Para debuggear |

### Comandos Django (se ejecutan DENTRO del contenedor)

| Comando | Qué hace | ¿Cuándo ejecutarlo? |
|---|---|---|
| `sudo docker-compose exec gateway python manage.py makemigrations persistence` | Genera los archivos de migración para los modelos (User, BlacklistedToken) | **Una sola vez** en la primera instalación |
| `sudo docker-compose exec gateway python manage.py migrate` | Crea las tablas en PostgreSQL a partir de las migraciones | **Una sola vez** al inicio, o cuando agregues/modifiques modelos |
| `sudo docker-compose exec gateway python manage.py seed_users` | **Dual-write:** crea los 3 usuarios seed en Gateway DB **y** en Artemisa con el **mismo UUID**. Requiere Artemisa corriendo. | **Una sola vez** después del primer migrate y con Artemisa activa |
| `sudo docker-compose exec gateway python manage.py cleanup_blacklisted_tokens` | Elimina tokens expirados de la tabla `blacklisted_tokens`. Soporta `--dry-run` y `--older-than-hours N`. | Periódicamente (cron, tarea programada) |
| `sudo docker-compose exec gateway python manage.py makemigrations` | Genera archivos de migración si cambiaste modelos | Solo si modificás `user_model.py` u otros modelos |
| `sudo docker-compose exec gateway python manage.py createsuperuser` | Crea un superusuario para el admin de Django | Opcional, si querés acceder a `/admin/` |

### Resumen: ¿Qué debo correr siempre?

```
Primera vez:                              Cada vez que trabajo:
──────────────────────────────           ─────────────────────
docker network create crm_network        docker-compose up -d
docker-compose up --build -d              (nada más)
docker-compose exec ... migrate
[levantar Artemisa + sus migraciones]
docker-compose exec ... seed_users       ← requiere Artemisa corriendo
```

> **Alternativa recomendada:** `./startup.sh` hace todo esto automáticamente.

**`migrate` y `seed_users` son comandos de UNA SOLA VEZ.** Los datos persisten en el volumen Docker `gateway_postgres_data`. Solo necesitás volver a ejecutarlos si:
- Borrás los volúmenes (`docker-compose down -v`) → repetir los comandos
- Agregás nuevos modelos o campos → solo `migrate`

---

## 5. Endpoints de la API

### Auth (Autenticación)

| Método | Ruta | Descripción | Auth? |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Login con email + password → retorna JWT | ❌ |
| `POST` | `/api/v1/auth/logout` | Invalida el token actual (blacklist) | ✅ |
| `GET` | `/api/v1/auth/me` | Retorna perfil del usuario autenticado | ✅ |

### Proxy — Usuarios (→ users-service)

| Método | Ruta | Roles permitidos |
|---|---|---|
| `GET` | `/api/v1/users/` | todos |
| `POST` | `/api/v1/users/` | admin |
| `GET` | `/api/v1/users/{id}/` | todos |
| `PUT` | `/api/v1/users/{id}/` | admin |
| `DELETE` | `/api/v1/users/{id}/` | admin |

### Proxy — Interacciones (→ interactions-service)

| Método | Ruta | Roles permitidos |
|---|---|---|
| `GET` | `/api/v1/interactions/` | todos |
| `POST` | `/api/v1/interactions/` | admin, soporte |
| `GET` | `/api/v1/interactions/{id}/` | todos |
| `PUT` | `/api/v1/interactions/{id}/` | admin, soporte |
| `DELETE` | `/api/v1/interactions/{id}/` | admin |
| `GET` | `/api/v1/interactions/client/{client_id}/` | todos |

### Health Check

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/v1/health/` | Estado del gateway y conectividad a microservicios |

### Formato de respuestas

Todas las respuestas siguen este formato estándar (envelope):

```json
// Éxito
{
  "success": true,
  "data": { ... },
  "message": "OK"
}

// Error
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Email o contraseña incorrectos"
  }
}
```

### Ejemplo de uso con cURL

```bash
# 1. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@crm.com", "password": "Temporal123!"}'

# Respuesta:
# {"success": true, "data": {"access_token": "eyJhbG...", "token_type": "Bearer"}, "message": "OK"}

# 2. Usar el token en endpoints protegidos
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbG..."

# 3. Logout
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer eyJhbG..."
```

---

## 6. Documentación Swagger (OpenAPI)

**Sí, la documentación Swagger está implementada.** Usa la librería `drf-spectacular` que genera automáticamente la especificación OpenAPI 3.0 a partir de los endpoints.

### URLs de documentación

| URL | Interfaz | Descripción |
|---|---|---|
| **http://localhost:8000/api/docs/** | Swagger UI | Interfaz interactiva para probar endpoints |
| **http://localhost:8000/api/redoc/** | ReDoc | Documentación en formato más legible/estático |
| **http://localhost:8000/api/schema/** | OpenAPI JSON | Esquema crudo (para importar en Postman, etc.) |

### Cómo acceder

1. Levantá el proyecto con `docker-compose up`
2. Ejecutá las migraciones si no lo hiciste
3. Abrí en el navegador: **http://localhost:8000/api/docs/**

### Qué vas a ver

- Cada endpoint documentado con su descripción, parámetros, request body y respuestas posibles
- Los endpoints están agrupados por tags: **Auth**, **Users (Proxy)**, **Interactions (Proxy)**, **Health**
- Podés probar los endpoints directamente desde la UI de Swagger
- Para endpoints protegidos: hacé clic en el candado 🔒 y pegá tu Bearer token

### Configuración

La configuración de Swagger está en `config/settings/base.py`:

```python
SPECTACULAR_SETTINGS = {
    'TITLE': 'CRM API Gateway',
    'DESCRIPTION': 'Punto de entrada único del CRM. Autenticación, autorización y routing a microservicios.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}
```

Cada vista tiene decoradores `@extend_schema` que agregan descripción, ejemplos y tipos de respuesta. Ejemplo de cómo se documenta un endpoint:

```python
@extend_schema(
    summary="Login de usuario",
    description="Autentica un usuario con email y contraseña. Retorna un JWT access token.",
    request=LoginRequestSerializer,
    responses={200: SuccessResponseSerializer, 401: ErrorResponseSerializer},
    tags=["Auth"],
)
def post(self, request): ...
```

---

## 7. Autenticación y JWT

### Flujo de autenticación

```
1. Cliente envía POST /api/v1/auth/login con {email, password}
2. Gateway busca el usuario en su BD local
3. Verifica la contraseña
4. Genera un JWT con los claims del usuario
5. Retorna el token al cliente
6. Cliente incluye "Authorization: Bearer <token>" en cada request
7. JWTMiddleware valida el token en cada request protegido
```

### Estructura del JWT

```json
{
  "sub": "uuid-del-usuario",     // ID único
  "email": "usuario@empresa.com", // Email
  "role": "admin",                // Rol (admin|soporte|comercial)
  "iat": 1700000000,              // Issued at (timestamp)
  "exp": 1700003600               // Expiration (timestamp)
}
```

- **Algoritmo:** HS256
- **Expiración:** configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: 60 min)
- **Secret:** configurable via `JWT_SECRET_KEY` en `.env`

### Blacklist de tokens (Logout)

Al hacer `POST /api/v1/auth/logout`, el token se agrega a la tabla `blacklisted_tokens`. El middleware revisa esa tabla antes de validar cada token.

---

## 8. Sistema de Permisos por Rol

### Los 3 roles

| Rol | Descripción |
|---|---|
| `admin` | Acceso total a todos los recursos |
| `soporte` | Lectura de usuarios, gestión de interacciones |
| `comercial` | Solo lectura de interacciones |

### Cómo funciona

Existe **un único archivo centralizado** con todos los permisos: `src/infrastructure/permissions/role_permissions.py`

```python
ROUTE_PERMISSIONS = {
    ('GET',    'users'):        ALL_ROLES,
    ('POST',   'users'):        [Role.ADMIN],
    ('DELETE', 'users'):        [Role.ADMIN],
    ('GET',    'interactions'): ALL_ROLES,
    ('POST',   'interactions'): [Role.ADMIN, Role.SOPORTE],
    # ... etc
}
```

La clase `RolePermission` (DRF `BasePermission`) extrae el recurso de la URL y consulta esta tabla. Si la combinación `(método, recurso)` no está en la tabla, **deniega por defecto** (fail-safe).

### Cómo modificar permisos

Para cambiar un permiso (ej: "soporte ahora puede eliminar usuarios"):

1. Abrí `src/infrastructure/permissions/role_permissions.py`
2. Modificá la línea correspondiente:
   ```python
   ('DELETE', 'users'): [Role.ADMIN, Role.SOPORTE],  # antes era solo ADMIN
   ```
3. No hace falta tocar ningún otro archivo.

---

## 9. Variables de Entorno

El archivo `.env` controla toda la configuración. Se copia desde `.env.example`:

| Variable | Descripción | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django (cambiar en producción) | `change-me-in-production` |
| `DJANGO_DEBUG` | Modo debug activado | `True` |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos | `localhost,127.0.0.1` |
| `DJANGO_SETTINGS_MODULE` | Módulo de settings a usar | `config.settings.local` |
| `DB_NAME` | Nombre de la base de datos | `crm_gateway_db` |
| `DB_USER` | Usuario de PostgreSQL | `postgres` |
| `DB_PASSWORD` | Contraseña de PostgreSQL | `postgres` |
| `DB_HOST` | Host de la BD (nombre del servicio Docker) | `db` |
| `DB_PORT` | Puerto de PostgreSQL | `5432` |
| `JWT_SECRET_KEY` | Clave secreta para firmar JWTs | `super-secret-jwt-key` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Minutos de validez del token | `60` |
| `JWT_ALGORITHM` | Algoritmo de firma | `HS256` |
| `USERS_SERVICE_URL` | URL interna del users-service | `http://users-service:8001` |
| `INTERACTIONS_SERVICE_URL` | URL interna del interactions-service | `http://interactions-service:8002` |
| `RATE_LIMIT_LOGIN` | Intentos de login por minuto | `5/minute` |
| `RATE_LIMIT_API` | Requests API por minuto | `100/minute` |
| `CORS_ALLOWED_ORIGINS` | Orígenes CORS permitidos (comma-separated). En desarrollo se configura en `local.py`. | `""` |

---

## 10. CORS

`django-cors-headers` permite a un frontend hacer peticiones al gateway desde otro origen.

### Configuración en development (Vite)

En `config/settings/local.py` están permitidos los orígenes del servidor de desarrollo de Vite:

```python
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]
```

Si usás un puerto diferente en Vite (`--port 3000`), agregálo a la lista.

### Configuración en producción

Usar la variable de entorno (separada por comas):

```env
CORS_ALLOWED_ORIGINS=https://mi-frontend.com,https://otro-dominio.com
```

### Headers permitidos

El header `Authorization` está incluido en `CORS_ALLOW_HEADERS`, por lo que los JWT pasan sin problema.
`CORS_ALLOW_CREDENTIALS = True` permite enviar cookies y el header `Authorization` en requests cross-origin.

### Uso desde Vite (fetch nativo)

```js
// Login
const res = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'admin@crm.com', password: 'Temporal123!' }),
})
const { data } = await res.json()
const token = data.access_token

// Petición autenticada
const users = await fetch('http://localhost:8000/api/v1/users/', {
  headers: { Authorization: `Bearer ${token}` },
})
```

---

## 10. Tests

### Ejecutar tests

```bash
# Desde el host (con venv activado)
cd Atenea
source venv/bin/activate
python -m pytest tests/ -v

# Desde dentro del contenedor Docker
sudo docker-compose exec gateway python -m pytest tests/ -v
```

Los tests usan **SQLite en memoria** (configurado en `config/settings/test.py`), así que no necesitan PostgreSQL.

### Estructura de tests

```
tests/
├── conftest.py                       # Fixtures compartidos
├── unit/
│   ├── test_login_use_case.py        # 5 tests — lógica de login (mock)
│   └── test_validate_token.py        # 5 tests — validación de JWT
└── integration/
    ├── test_auth_endpoints.py        # 11 tests — endpoints de auth
    └── test_gateway_proxy.py         # 14 tests — proxy y permisos
```

### Qué cubre cada test

**Unit — Login (5 tests):**
- ✅ Login exitoso → retorna token con claims correctos
- ❌ Email inexistente → `InvalidCredentialsError`
- ❌ Contraseña incorrecta → `InvalidCredentialsError`
- ❌ Usuario inactivo → `InvalidCredentialsError`
- ✅ Token tiene expiración correcta

**Unit — Validate Token (5 tests):**
- ✅ Token válido → retorna claims
- ❌ Token expirado → `TokenExpiredError`
- ❌ Token malformado → `TokenInvalidError`
- ❌ Token con secret incorrecto → `TokenInvalidError`
- ❌ Token vacío → `TokenInvalidError`

**Integration — Auth Endpoints (11 tests):**
- ✅ Login exitoso → 200 + token
- ❌ Email inexistente → 401
- ❌ Contraseña incorrecta → 401
- ❌ Body incompleto → 422
- ❌ Body vacío → 422
- ❌ 6 intentos consecutivos → 429 (rate limit)
- ✅ Logout exitoso → 200
- ❌ Logout sin token → 401
- ✅ GET /me con token → perfil
- ❌ GET /me sin token → 401
- ❌ GET /me con token expirado → 401
- ❌ GET /me con token malformado → 401

**Integration — Gateway Proxy (14 tests):**
- ✅ Admin puede DELETE /users/ → 204
- ❌ Soporte no puede DELETE /users/ → 403
- ❌ Comercial no puede DELETE /users/ → 403
- ✅ Admin puede GET /users/ → 200
- ✅ Soporte puede GET /users/ → 200
- ✅ Comercial puede GET /users/ → 200
- ✅ Proxy envía headers internos (X-User-Id, X-User-Role)
- ❌ Microservicio caído → 503
- ✅ Token válido accede a endpoint protegido
- ❌ Token expirado → 401
- ❌ Sin token → 401
- ❌ Token malformado → 401

**Total: 35 tests**

---

## 11. Estructura de Archivos Explicada

```
Atenea/
├── config/                              # Configuración Django
│   ├── settings/
│   │   ├── base.py                      # Settings compartidos (apps, middleware, DRF, JWT, etc.)
│   │   ├── local.py                     # Settings de desarrollo (DEBUG=True, logs consola)
│   │   ├── production.py                # Settings producción (DEBUG=False, logs JSON)
│   │   └── test.py                      # Settings tests (SQLite en memoria, hashers rápidos)
│   ├── urls.py                          # Rutas raíz (auth, gateway, health, docs)
│   └── wsgi.py                          # Entry point WSGI (Gunicorn lo usa en producción)
│
├── src/
│   ├── domain/                           # 🟢 DOMINIO — Python puro, SIN frameworks
│   │   ├── entities/
│   │   │   ├── token.py                 # Entidad Token (access_token, token_type)
│   │   │   └── user.py                  # Entidad User (id, email, role, password_hash)
│   │   ├── exceptions.py                # Excepciones de dominio (InvalidCredentials, etc.)
│   │   └── ports/
│   │       ├── inbound/
│   │       │   └── auth_service_port.py  # ABC: contrato para autenticación
│   │       └── outbound/
│   │           ├── user_repository_port.py     # ABC: contrato para acceso a usuarios
│   │           └── password_verifier_port.py   # ABC: contrato para verificar contraseñas
│   │
│   ├── application/                      # 🟢 APLICACIÓN — Casos de uso (Python puro)
│   │   └── use_cases/
│   │       ├── login_user.py             # Caso de uso: buscar user → verificar password → emitir JWT
│   │       ├── validate_token.py         # Caso de uso: decodificar y validar JWT
│   │       └── create_user_gateway.py    # Caso de uso: ★ dual-write (Gateway DB + Artemisa, rollback)
│   │
│   ├── adapters/
│   │   ├── inbound/http/                # 🔵 Adaptadores de entrada (reciben requests HTTP)
│   │   │   ├── auth/
│   │   │   │   ├── views.py             # LoginView, LogoutView, MeView
│   │   │   │   ├── serializers.py       # Validación de request/response
│   │   │   │   └── urls.py              # /api/v1/auth/*
│   │   │   ├── gateway/
│   │   │   │   ├── views.py             # UserProxyView (dual-write), ClientProxyView (proxy), InteractionProxyView
│   │   │   │   ├── serializers.py       # Serializers para documentación Swagger
│   │   │   │   └── urls.py              # /api/v1/users/*, /api/v1/clients/*, /api/v1/interactions/*
│   │   │   ├── health/
│   │   │   │   ├── views.py             # HealthView
│   │   │   │   └── urls.py              # /api/v1/health/
│   │   │   └── exception_handler.py     # Handler global de errores (envelope estándar)
│   │   │
│   │   └── outbound/                    # 🟡 Adaptadores de salida (llaman a servicios externos)
│   │       ├── persistence/
│   │       │   ├── models/
│   │       │   │   ├── user_model.py             # Django ORM: tabla users
│   │       │   │   └── blacklisted_token_model.py # Django ORM: tabla blacklisted_tokens
│   │       │   ├── django_user_repository.py      # Implementa UserRepositoryPort con Django ORM
│   │       │   ├── django_password_verifier.py    # Implementa PasswordVerifierPort con Django
│   │       │   ├── apps.py                        # Config del app Django
│   │       │   └── management/commands/
│   │       │       ├── seed_users.py              # Comando: crear usuarios iniciales (dual-write: Gateway + Artemisa)
│   │       │       ├── seed_clients.py            # Comando: crear clientes iniciales (POST directo a Artemisa)
│   │       │       └── cleanup_blacklisted_tokens.py # Comando: limpiar tokens expirados de la blacklist
│   │       └── http_client/
│   │           ├── users_client.py                # httpx async → users-service
│   │           └── interactions_client.py         # httpx async → interactions-service
│   │
│   └── infrastructure/                  # 🟠 Infraestructura transversal
│       ├── middleware/
│       │   ├── jwt_middleware.py         # Valida Bearer token en cada request
│       │   ├── jwt_authentication.py    # Puente JWT → DRF authentication
│       │   ├── rate_limit_middleware.py  # Limita requests por IP
│       │   └── logging_middleware.py     # Log JSON de cada request/response
│       ├── permissions/
│       │   ├── role_permissions.py       # TABLA CENTRALIZADA de permisos por rol
│       │   └── role_permission.py        # DRF BasePermission que consulta la tabla
│       ├── logging/
│       │   └── setup.py                  # Configuración de structlog
│       └── di/
│           └── container.py              # Inyección de dependencias (ensambla use cases)
│
├── tests/                               # 🧪 Tests
│   ├── conftest.py                      # Fixtures: usuarios, tokens, clientes auth
│   ├── unit/                            # Tests de lógica pura (con mocks)
│   └── integration/                     # Tests de endpoints reales
│
├── docs/                                # 📖 Documentación
├── Dockerfile                           # Imagen Docker del gateway
├── docker-compose.yml                   # Orquestación gateway + postgres
├── requirements.txt                     # Dependencias Python (pip freeze)
├── .env.example                         # Template de variables de entorno
├── .env                                 # Variables de entorno LOCAL (no commitear)
├── manage.py                            # CLI de Django
└── pytest.ini                           # Configuración de pytest
```

---

## 12. Preguntas Frecuentes (FAQ)

### ¿Debo correr `migrate` y `seed_users` cada vez que levanto Docker?

**No.** Son comandos de una sola vez. Los datos persisten en el volumen Docker `gateway_postgres_data`. Solo repetí estos comandos si:
- Ejecutaste `docker-compose down -v` (que borra los volúmenes)
- Agregaste o modificaste modelos Django (solo `migrate`)
- `seed_users` requiere además que **Artemisa esté corriendo** ya que hace dual-write.

### ¿Qué pasa si el users-service o interactions-service no están corriendo?

Los endpoints de proxy (`/api/v1/users/`, `/api/v1/interactions/`) retornarán un error 503:
```json
{
  "success": false,
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "El servicio de usuarios no está disponible"
  }
}
```
Los endpoints de auth (`/login`, `/logout`, `/me`) y health (`/health/`) funcionan independientemente.

### ¿Dónde está Swagger?

En **http://localhost:8000/api/docs/** (con el servidor corriendo).

### ¿Cuáles son los usuarios de prueba?

| Email | Contraseña | Rol |
|---|---|---|
| `admin@crm.com` | `Temporal123!` | admin |
| `soporte@crm.com` | `Temporal123!` | soporte |
| `comercial@crm.com` | `Temporal123!` | comercial |

Se crean con `python manage.py seed_users` desde Atenea. El comando usa dual-write: crea cada usuario en la Gateway DB (con password hash) **y** en Artemisa (mismo UUID, sin password) en una sola operación. Artemisa debe estar corriendo cuando se ejecuta.

### ¿Cuándo necesito `--build` en docker-compose?

Solo cuando modifiques:
- `Dockerfile`
- `requirements.txt` (nuevas dependencias)

Si solo cambiás código Python, con `docker-compose up` basta (el volumen sincroniza archivos).

### ¿Cómo cambiar la expiración del token?

Editá `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` en `.env`:
```env
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=120  # 2 horas
```

### ¿Cómo agrego un nuevo rol?

1. Agregá la opción en `src/adapters/outbound/persistence/models/user_model.py` → `ROLE_CHOICES`
2. Agregá el enum en `src/infrastructure/permissions/role_permissions.py` → `Role`
3. Asigná permisos en `ROUTE_PERMISSIONS`
4. Ejecutá `makemigrations` + `migrate`

### ¿Cómo agrego un nuevo microservicio?

1. Creá un nuevo client en `src/adapters/outbound/http_client/`
2. Creá la view proxy en `src/adapters/inbound/http/gateway/`
3. Agregá las rutas en `urls.py`
4. Agregá los permisos en `ROUTE_PERMISSIONS`
5. Agregá la URL en `.env`
