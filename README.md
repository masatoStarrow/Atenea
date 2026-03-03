# Atenea — CRM API Gateway

Punto de entrada único del CRM empresarial. Autenticación JWT, autorización por roles, rate limiting, logging estructurado y **dual-write** de usuarios hacia el microservicio de usuarios.

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Framework | Django 6.0.2 + Django REST Framework |
| Lenguaje | Python 3.13 |
| Base de datos | PostgreSQL 15 |
| Autenticación | PyJWT (access token HS256) |
| HTTP Client | httpx 0.28 (async) |
| CORS | django-cors-headers 4.7.0 |
| Documentación | drf-spectacular (Swagger UI + ReDoc) |
| Logging | structlog (JSON estructurado) |
| Testing | pytest + pytest-django |
| Containerización | Docker + docker-compose |

---

## Arquitectura hexagonal

```
src/
├── core/                                  # DOMINIO — cero imports de frameworks
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── token.py                   # TokenEntity: access_token, token_type
│   │   │   └── user.py                    # UserEntity: id, email, full_name, role, is_active, password_hash
│   │   └── exceptions.py                  # 7 excepciones de dominio (ver tabla abajo)
│   ├── ports/
│   │   ├── inbound/
│   │   │   └── auth_service_port.py       # ABC login
│   │   └── outbound/
│   │       ├── password_verifier_port.py  # ABC verify password
│   │       └── user_repository_port.py    # ABC: get_by_email, get_by_id, create, update, deactivate, delete_by_id
│   └── use_cases/
│       ├── login_user.py                  # Buscar user → verificar password → emitir JWT
│       ├── validate_token.py              # Decodificar y validar JWT
│       └── create_user_gateway.py         # ★ Dual-write: Gateway DB + users-service
│
├── adapters/
│   ├── inbound/http/
│   │   ├── auth/                          # POST /login, POST /logout, GET /me
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   ├── gateway/                       # Proxy + dual-write hacia microservicios
│   │   │   ├── views.py                   # UserProxyView (dual-write), ClientProxyView (proxy), InteractionProxyView
│   │   │   ├── serializers.py             # Serializers para Swagger (CreateUser, CreateClient, etc.)
│   │   │   └── urls.py
│   │   └── health/                        # GET /api/v1/health/
│   └── outbound/
│       ├── persistence/
│       │   ├── models/
│       │   │   ├── user_model.py          # Django User (AbstractBaseUser, UUID PK)
│       │   │   └── blacklisted_token_model.py
│       │   ├── django_user_repository.py  # CRUD completo con structlog
│       │   ├── django_password_verifier.py
│       │   └── management/commands/
│       │       ├── seed_users.py          # ★ Dual-write seed: crea usuarios en Gateway DB + Artemisa
│       │       ├── seed_clients.py        # Seed clientes → POST directo a Artemisa (no dual-write)
│       │       └── cleanup_blacklisted_tokens.py  # Limpia tokens expirados de la blacklist
│       └── http_client/
│           ├── users_client.py            # httpx async → crm-users-service
│           └── interactions_client.py     # httpx async → crm-interactions-service
│
└── infrastructure/
    ├── middleware/
    │   ├── jwt_middleware.py              # Valida Bearer token en cada request
    │   ├── jwt_authentication.py          # DRF Authentication backend
    │   ├── rate_limit_middleware.py        # Rate limiting por IP/usuario
    │   └── logging_middleware.py           # Log estructurado request/response
    ├── permissions/
    │   ├── role_permissions.py            # Tabla centralizada ROUTE_PERMISSIONS
    │   └── role_permission.py             # DRF BasePermission
    ├── logging/setup.py
    └── di/container.py                    # Inyección de dependencias
```

---

## Endpoints

### Auth (públicos)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/auth/login` | Login con email + password → JWT token |
| POST | `/api/v1/auth/logout` | Invalida token (blacklist) |
| GET | `/api/v1/auth/me` | Perfil del usuario autenticado |

### Users — Dual-Write (requieren JWT + rol)

| Método | Ruta | Descripción | Comportamiento |
|---|---|---|---|
| GET | `/api/v1/users/` | Listar usuarios | Proxy puro → users-service |
| POST | `/api/v1/users/` | Crear usuario | **Dual-write**: Gateway DB (con password) + users-service (sin password). Mismo UUID. Rollback si falla. |
| GET | `/api/v1/users/{id}/` | Obtener usuario | Proxy puro → users-service |
| PUT | `/api/v1/users/{id}/` | Actualizar usuario | **Dual-write**: actualiza Gateway DB + proxy a users-service |
| DELETE | `/api/v1/users/{id}/` | Eliminar usuario | **Dual-write**: desactiva en Gateway DB + proxy DELETE a users-service |

### Interactions — Proxy puro

| Método | Ruta | Roles |
|---|---|---|
| GET | `/api/v1/interactions/` | admin, soporte, comercial |
| POST | `/api/v1/interactions/` | admin, soporte |
| GET | `/api/v1/interactions/{id}/` | admin, soporte, comercial |
| PUT | `/api/v1/interactions/{id}/` | admin, soporte |
| DELETE | `/api/v1/interactions/{id}/` | admin |
| GET | `/api/v1/interactions/client/{client_id}/` | admin, soporte, comercial |

### Clients — Proxy puro (requieren JWT + rol)

| Método | Ruta | Roles | Descripción |
|---|---|---|---|
| GET | `/api/v1/clients/` | admin, soporte, comercial | Listar clientes. Filtro: `status`. Paginación: `page`, `page_size` |
| POST | `/api/v1/clients/` | admin, soporte | Crear cliente. Campos: `company` (req), `email` (req), `phone`, `status` |
| GET | `/api/v1/clients/{id}/` | admin, soporte, comercial | Obtener cliente por ID |
| PUT | `/api/v1/clients/{id}/` | admin, soporte | Actualizar datos del cliente |
| DELETE | `/api/v1/clients/{id}/` | admin | Soft delete → `status='inactive'` |

### Health

| Método | Ruta |
|---|---|
| GET | `/api/v1/health/` |

---

## Flujo Dual-Write (creación de usuario)

```
Cliente (Swagger / Frontend)
    │
    ▼
POST /api/v1/users/  { email, full_name, role, password }
    │
    ▼
┌─────────────────── API Gateway (Atenea) ───────────────────┐
│                                                             │
│  1. Genera UUID compartido                                  │
│  2. INSERT en Gateway DB (uuid, email, password_hash, role) │
│  3. POST → users-service  { id: uuid, email, full_name,    │
│                              role }  (SIN password)         │
│  4. Si falla → DELETE del registro local (rollback)         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
    │                                    │
    ▼                                    ▼
Gateway DB (PostgreSQL)          Users Service (Artemisa)
 ✔ uuid + password_hash          ✔ mismo uuid, sin password
```

> **La contraseña NUNCA sale del Gateway.** Solo se almacena como hash en la base de datos local.

---

## Permisos por rol

Tabla centralizada en `src/infrastructure/permissions/role_permissions.py`:

| Recurso | GET | POST | PUT | DELETE |
|---|---|---|---|---|
| users | admin, soporte | admin | admin | admin |
| clients | todos | admin, soporte | admin, soporte | admin |
| interactions | todos | admin, soporte | admin, soporte | admin |

---

## Excepciones de dominio

| Excepción | Código | HTTP |
|---|---|---|
| `InvalidCredentialsError` | `INVALID_CREDENTIALS` | 401 |
| `TokenExpiredError` | `TOKEN_EXPIRED` | 401 |
| `TokenInvalidError` | `TOKEN_INVALID` | 401 |
| `UnauthorizedError` | `UNAUTHORIZED` | 403 |
| `EmailAlreadyExistsError` | `EMAIL_ALREADY_EXISTS` | 409 |
| `UserNotFoundError` | `USER_NOT_FOUND` | 404 |
| `ServiceUnavailableError` | `SERVICE_UNAVAILABLE` | 503 |

---

## Documentación API (Swagger)

| URL | Tipo |
|---|---|
| `/api/docs/` | Swagger UI |
| `/api/redoc/` | ReDoc |
| `/api/schema/` | OpenAPI JSON/YAML |

---

## Docker

```bash
# Levantar
docker-compose up -d --build

# Migraciones
docker-compose exec gateway python manage.py migrate

# Tests
docker-compose exec gateway python -m pytest tests/ -v

# Seed de usuarios (dual-write: crea en Gateway DB Y en Artemisa con el mismo UUID)
# ⚠️  Artemisa debe estar corriendo antes de ejecutar esto
docker-compose exec gateway python manage.py seed_users

# Seed de clientes (POST directo a Artemisa — no dual-write)
# ⚠️  Artemisa debe estar corriendo antes de ejecutar esto
docker-compose exec gateway python manage.py seed_clients
```

Usuarios seed: `admin@crm.com`, `soporte@crm.com`, `comercial@crm.com` (password: `Temporal123!`)

Clientes seed: `Acme Corporation`, `Globex Industries`, `Stark Enterprises`, `Wayne Technologies`, `Umbrella Corp`

---

## CORS (acceso desde el frontend)

`django-cors-headers` está configurado para permitir peticiones desde el servidor de desarrollo de Vite por defecto.

| Origen permitido (development) | Puerto |
|---|---|
| `http://localhost:5173` | Vite dev server |
| `http://127.0.0.1:5173` | Vite dev server |

Para agregar más orígenes en producción, usar la variable de entorno:
```env
CORS_ALLOWED_ORIGINS=https://mi-frontend.com,https://otro.com
```

---

## Script de inicio automático

Usar `startup.sh` para levantar todo el sistema CRM con un solo comando:

```bash
cd Atenea
./startup.sh               # Levanta todo + migraciones + seed + tests
./startup.sh --skip-tests  # Levanta todo + migraciones + seed (sin tests)
./startup.sh --help        # Ver todas las opciones
```

El script:
1. Limpia contenedores existentes
2. Crea la red Docker `crm_network`
3. Levanta Atenea + aplica migraciones
4. Levanta Artemisa + aplica migraciones
5. Espera a que Artemisa responda en `/health/`
6. Ejecuta `seed_users` (dual-write: mismo UUID en ambas BDs)
7. Ejecuta `seed_clients` (POST directo a Artemisa)
8. Corre los tests (opcional)

---

## Red compartida

Ambos servicios comparten la red Docker `crm_network` para comunicación interna:

```yaml
networks:
  crm_network:
    external: true
```

```bash
# Crear la red (una sola vez)
docker network create crm_network
```

---

## Variables de entorno (.env)

```env
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=crm_gateway_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

JWT_SECRET_KEY=super-secret-jwt-key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_ALGORITHM=HS256

USERS_SERVICE_URL=http://users-service:8001/api/v1
INTERACTIONS_SERVICE_URL=http://interactions-service:8002
```

---

## Tests

**48 tests** — 0 failures

```
tests/
├── conftest.py                          # Fixtures: usuarios por rol, tokens JWT, API clients
├── unit/
│   ├── test_login_use_case.py           # 5 tests — lógica pura de login
│   ├── test_validate_token.py           # 5 tests — tokens válidos/expirados/malformados
│   └── test_create_user_gateway.py      # 6 tests — dual-write: happy path, rollback, UUID match
└── integration/
    ├── test_auth_endpoints.py           # 7 tests — login, logout, me
    ├── test_gateway_proxy.py            # 13 tests — permisos, headers, proxy, tokens
    └── test_dual_write.py              # 12 tests — create/update/delete con dual-write
```
