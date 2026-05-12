# Atenea — CRM API Gateway

Punto de entrada único del CRM empresarial. **Toda petición del frontend pasa por aquí.** Se encarga de:

- **Autenticación** — Login con email + password → JWT token
- **Autorización** — Permisos por rol (admin, soporte, comercial) en cada endpoint
- **Rate limiting** — 5 req/min para login, 100 req/min para API
- **Proxy** — Reenvía peticiones a los microservicios internos (Artemisa para usuarios/clientes, Venus para interacciones)
- **Dual-write** — Al crear usuarios, guarda en su BD local (con password) Y en Artemisa (sin password), usando el mismo UUID
- **Logging estructurado** — Trazabilidad completa request/response con structlog

---

## Tabla de contenidos

- [Stack tecnológico](#stack-tecnológico)
- [¿Por qué Clean Architecture (Bancolombia)?](#por-qué-clean-architecture-bancolombia)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Flujo de autenticación](#flujo-de-autenticación)
- [Flujo Dual-Write](#flujo-dual-write-creación-de-usuario)
- [Endpoints](#endpoints)
- [Permisos por rol](#permisos-por-rol)
- [Middleware stack](#middleware-stack)
- [Excepciones de dominio](#excepciones-de-dominio)
- [Docker](#docker)
- [Tests](#tests)
- [CORS](#cors-acceso-desde-el-frontend)
- [Script de inicio automático](#script-de-inicio-automático)
- [Documentación API (Swagger)](#documentación-api-swagger)

---

## Stack tecnológico

| Componente | Tecnología | Versión |
|---|---|---|
| Framework | Django + Django REST Framework | 6.0.2 + 3.16.1 |
| Lenguaje | Python | 3.13 |
| Base de datos | PostgreSQL | 15 |
| Autenticación | PyJWT (HS256) | Access tokens |
| HTTP Client | httpx (async) | 0.28 |
| CORS | django-cors-headers | 4.7.0 |
| Documentación | drf-spectacular | Swagger UI + ReDoc |
| Logging | structlog | JSON estructurado |
| Testing | pytest + pytest-django | — |
| Containerización | Docker + docker-compose | — |

---

## ¿Por qué Clean Architecture (Bancolombia)?

Este proyecto sigue los principios de [**Clean Architecture propuestos por Bancolombia**](https://bancolombia.github.io/scaffold-clean-architecture/docs/intro), adaptados de Java/Gradle a Python/Django.

### Motivación

1. **Regla de dependencia:** las capas internas (dominio, aplicación) **no importan Django, DRF ni ningún framework**. Si mañana cambiamos Django por Flask, solo se reescriben los adaptadores — la lógica de autenticación queda intacta.
2. **Testabilidad:** los casos de uso (`login_user`, `validate_token`, `create_user_gateway`) se prueban con mocks puros — sin necesidad de levantar Django ni base de datos.
3. **Separación de responsabilidades:** las vistas de DRF solo traducen HTTP → caso de uso → respuesta HTTP. No contienen lógica de negocio.
4. **Escalabilidad del equipo:** diferentes personas pueden trabajar en middleware, vistas proxy y casos de uso sin pisarse.

### Mapeo Bancolombia → Python/Django

| Capa Bancolombia | Módulo Bancolombia | Nuestro equivalente | Qué contiene |
|---|---|---|---|
| **Domain** | `model` | `src/domain/` | Entidades (Token, User), puertos (ABCs), excepciones |
| **Domain** | `usecase` | `src/application/` | Casos de uso: login, validate_token, create_user_gateway |
| **Infrastructure** | `entry-points` | `src/adapters/inbound/` | Vistas DRF (auth, gateway, health), serializers |
| **Infrastructure** | `driven-adapters` | `src/adapters/outbound/` | Repos Django ORM, password verifier, httpx clients, management commands |
| **Infrastructure** | `helpers` | `src/infrastructure/` | Middleware (JWT, rate limit, logging), permisos, DI, logging |
| **Application** | `app-service` | `manage.py` + `config/` | Entry point Django, settings por ambiente |

### Diagrama de capas

```
┌─────────────────────────────────────────────────────────┐
│              manage.py + config/settings/                │  ← Entry point
├─────────────────────────────────────────────────────────┤
│  infrastructure/                                        │  ← Middleware stack
│  (JWT, rate limit, logging, permisos)                   │
├─────────────────────────────────────────────────────────┤
│  adapters/inbound/    │    adapters/outbound/           │  ← Frameworks
│  (vistas DRF)         │    (Django ORM, httpx)          │
├───────────────────────┴─────────────────────────────────┤
│                  application/                            │  ← Python puro
│          (casos de uso: login, validate, dual-write)     │
├─────────────────────────────────────────────────────────┤
│                    domain/                               │  ← Python puro
│       (entidades, ports, excepciones)                    │
└─────────────────────────────────────────────────────────┘
         Las flechas de dependencia apuntan hacia adentro →
```

---

## Estructura del proyecto

```
Atenea/
├── manage.py                       # Entry point Django
├── startup.sh                      # Script que levanta TODO el sistema CRM
├── config/
│   ├── urls.py                     # URL routing principal: auth, gateway, health, docs
│   ├── asgi.py / wsgi.py           # Interfaces ASGI/WSGI
│   └── settings/
│       ├── base.py                 # Settings compartidos: JWT, DRF, middleware stack, BD
│       ├── local.py                # Settings para desarrollo local (DEBUG=True)
│       ├── production.py           # Settings para producción
│       └── test.py                 # Settings para tests (SQLite en memoria)
│
├── src/
│   │
│   ├── domain/                     # 🟢 CAPA DOMINIO — Python puro, CERO frameworks
│   │   │
│   │   ├── entities/               # Representan los conceptos principales
│   │   │   ├── token.py            #   → TokenEntity: access_token, token_type="Bearer"
│   │   │   └── user.py             #   → UserEntity: id, email, full_name, role, is_active,
│   │   │                           #                  password_hash (solo aquí se guarda password)
│   │   │
│   │   ├── ports/                  # Contratos (interfaces ABC) — definen QUÉ se puede hacer
│   │   │   ├── inbound/
│   │   │   │   └── auth_service_port.py  # → ABC: login(email, password) → Token
│   │   │   └── outbound/
│   │   │       ├── user_repository_port.py    # → ABC: get_by_email, get_by_id, create,
│   │   │       │                              #   update, deactivate, delete_by_id (rollback)
│   │   │       └── password_verifier_port.py  # → ABC: verify(plain, hash) → bool
│   │   │
│   │   └── exceptions.py          # 7 excepciones de dominio (ver tabla abajo)
│   │
│   ├── application/                # 🔵 CAPA APLICACIÓN — Python puro, orquesta la lógica
│   │   └── use_cases/
│   │       ├── login_user.py           # → Buscar user → verificar password → emitir JWT
│   │       ├── validate_token.py       # → Decodificar JWT (stateless, sin BD)
│   │       └── create_user_gateway.py  # → ★ Dual-write: Gateway DB (con password)
│   │                                   #   + POST a Artemisa (sin password). Rollback si falla.
│   │
│   ├── adapters/                   # 🟡 CAPA ADAPTADORES — aquí SÍ se usan frameworks
│   │   │
│   │   ├── inbound/http/           # === Entry Points (reciben peticiones HTTP) ===
│   │   │   ├── auth/               # Endpoints de autenticación
│   │   │   │   ├── views.py        #   → LoginView (POST), LogoutView (POST), MeView (GET)
│   │   │   │   ├── serializers.py  #   → LoginSerializer, TokenResponseSerializer
│   │   │   │   └── urls.py         #   → /api/v1/auth/login, /logout, /me
│   │   │   │
│   │   │   ├── gateway/            # Proxy + dual-write hacia microservicios
│   │   │   │   ├── views.py        #   → UserProxyView: ★ dual-write en POST/PUT/DELETE
│   │   │   │   │                   #   → ClientProxyView: proxy puro a Artemisa
│   │   │   │   │                   #   → InteractionProxyView: proxy puro a Venus (CRUD)
│   │   │   │   │                   #   → InteractionMetricsProxyView: métricas globales
│   │   │   │   │                   #   → InteractionClientSummaryProxyView: resumen por cliente
│   │   │   │   │                   #   → InteractionFollowUpsProxyView: seguimientos
│   │   │   │   │                   #   → InteractionCloseProxyView: cerrar interacción
│   │   │   │   │                   #   → InteractionAuditProxyView: historial de cambios
│   │   │   │                   #   → InteractionAttachmentProxyView: adjuntos (upload, list, download, delete)
│   │   │   │   ├── serializers.py  #   → Serializers para documentación Swagger
│   │   │   │   └── urls.py         #   → /api/v1/users/, /clients/, /interactions/*
│   │   │   │
│   │   │   ├── health/             # Health check
│   │   │   │   ├── views.py        #   → GET /api/v1/health/
│   │   │   │   └── urls.py
│   │   │   │
│   │   │   ├── exception_handler.py # → Handler global: DomainException → JSON response
│   │   │   └── validators.py       # → Validaciones compartidas de entrada
│   │   │
│   │   └── outbound/               # === Driven Adapters (acceden a BD y servicios externos) ===
│   │       ├── persistence/
│   │       │   ├── models/
│   │       │   │   ├── user_model.py              # → Django User (AbstractBaseUser, UUID PK)
│   │       │   │   └── blacklisted_token_model.py # → Tokens invalidados (logout)
│   │       │   ├── django_user_repository.py      # → CRUD completo con structlog
│   │       │   ├── django_password_verifier.py    # → Verifica bcrypt hash
│   │       │   └── management/commands/
│   │       │       ├── seed_users.py              # → ★ Dual-write seed: crea usuarios en
│   │       │       │                              #   Gateway DB + Artemisa (mismo UUID)
│   │       │       ├── seed_clients.py            # → Seed clientes: POST directo a Artemisa
│   │       │       ├── seed_interactions.py       # → Seed interacciones: POST directo a Venus
│   │       │       └── cleanup_blacklisted_tokens.py # → Limpia tokens expirados
│   │       │
│   │       └── http_client/        # Clientes HTTP hacia microservicios internos
│   │           ├── users_client.py       # → httpx async → Artemisa (port 8001)
│   │           └── interactions_client.py # → httpx async → Venus (port 8002)
│   │
│   └── infrastructure/             # 🟠 HELPERS — utilidades transversales
│       ├── middleware/
│       │   ├── jwt_middleware.py         # → Valida Bearer token en cada request
│       │   │                            #   Public paths: /auth/login, /health/, /docs/
│       │   ├── jwt_authentication.py    # → DRF Authentication backend
│       │   ├── rate_limit_middleware.py  # → Rate limiting: 5/min login, 100/min API
│       │   └── logging_middleware.py     # → Log estructurado request/response
│       ├── permissions/
│       │   ├── role_permissions.py  # → ★ Tabla centralizada ROUTE_PERMISSIONS
│       │   │                        #   (método, recurso) → [roles permitidos]
│       │   └── role_permission.py   # → DRF BasePermission que consulta la tabla
│       ├── logging/
│       │   └── setup.py            #   → Configuración structlog (JSON)
│       └── di/
│           └── container.py        #   → Fábricas DI: get_login_use_case(), get_validate_token_use_case()
│
└── tests/
    ├── conftest.py                 # Fixtures: usuarios por rol, tokens JWT, API clients
    ├── unit/
    │   ├── test_login_use_case.py       #  5 tests — login: happy path, credenciales inválidas
    │   ├── test_validate_token.py       #  5 tests — tokens válidos/expirados/malformados
    │   └── test_create_user_gateway.py  #  6 tests — dual-write: happy path, rollback, UUID match
    └── integration/
        ├── test_auth_endpoints.py       #  7 tests — login, logout, me via HTTP
        ├── test_gateway_proxy.py        # 13 tests — permisos, headers, proxy, tokens
        ├── test_dual_write.py           # 12 tests — create/update/delete con dual-write
        └── test_client_endpoints.py     # 26 tests — CRUD clientes, permisos, filtros
```

### ¿Qué hace cada capa? (explicación rápida)

| Capa | Carpeta | ¿Importa frameworks? | Responsabilidad |
|---|---|---|---|
| **Dominio** | `src/domain/` | ❌ Python puro | Define qué es un token, qué es un usuario, qué errores de autenticación existen, y qué contratos deben cumplir los repos y servicios |
| **Aplicación** | `src/application/` | ❌ Python puro | Orquesta: `login_user` busca user → verifica password → emite JWT. `create_user_gateway` hace dual-write con rollback |
| **Adaptadores** | `src/adapters/` | ✅ DRF, Django ORM, httpx | Vistas HTTP (auth + gateway proxy), repositorios Django, clientes httpx hacia microservicios, management commands |
| **Infraestructura** | `src/infrastructure/` | ✅ Django middleware | Middleware stack (JWT, rate limit, logging), tabla de permisos por rol, inyección de dependencias |

---

## Flujo de autenticación

```
1. Frontend envía POST /api/v1/auth/login  { email, password }
       │
2. JWTMiddleware → path es público → deja pasar sin token
       │
3. LoginView → llama a LoginUser use case
       │
4. LoginUser:
   a) Busca usuario por email (UserRepository)
   b) Verifica password (PasswordVerifier → bcrypt)
   c) Genera JWT con claims: { sub: user_id, email, role, exp }
   d) Retorna TokenEntity (access_token, token_type="Bearer")
       │
5. LoginView → serializa y retorna al frontend
       │
6. Frontend guarda el token y lo envía en cada petición:
   Authorization: Bearer <token>
       │
7. JWTMiddleware intercepta:
   a) Verifica que no esté en blacklist
   b) Decodifica con ValidateToken use case
   c) Busca el User en la BD y lo inyecta en request.user
   d) Inyecta headers internos: X-User-Id, X-User-Role, X-Request-Id
       │
8. RolePermission verifica: ¿este rol tiene acceso a este método+recurso?
       │
9. La vista proxy reenvía al microservicio interno con los headers
```

---

## Flujo Dual-Write (creación de usuario)

El Gateway es la **única fuente de verdad para passwords**. Cuando se crea un usuario, se guarda en dos bases de datos con el mismo UUID:

```
POST /api/v1/users/  { email, full_name, role, password }
       │
       ▼
┌─────────────────── API Gateway (Atenea) ───────────────────┐
│                                                             │
│  1. Genera UUID compartido                                  │
│  2. INSERT en Gateway DB (uuid, email, password_hash, role) │
│  3. POST → Artemisa: { id: uuid, email, full_name, role }  │
│     (SIN password)                                          │
│  4. Si Artemisa falla → DELETE del registro local (rollback)│
│                                                             │
└─────────────────────────────────────────────────────────────┘
       │                                    │
       ▼                                    ▼
  Gateway DB (PostgreSQL)           Artemisa (PostgreSQL)
   ✔ uuid + password_hash           ✔ mismo uuid, sin password
```

> **La contraseña NUNCA sale del Gateway.** Solo se almacena como hash bcrypt en la BD local de Atenea.

---

## Endpoints

### Auth (públicos — no requieren token)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Login con email + password → JWT token |
| `POST` | `/api/v1/auth/logout` | Invalida token (blacklist) |
| `GET` | `/api/v1/auth/me` | Perfil del usuario autenticado |

### Users — Dual-Write (requieren JWT + rol)

| Método | Ruta | Comportamiento |
|---|---|---|
| `GET` | `/api/v1/users/` | Proxy puro → Artemisa |
| `POST` | `/api/v1/users/` | **Dual-write**: Gateway DB (con password) + Artemisa (sin password). Rollback si falla. |
| `GET` | `/api/v1/users/{id}/` | Proxy puro → Artemisa |
| `PUT` | `/api/v1/users/{id}/` | **Dual-write**: actualiza Gateway DB + proxy a Artemisa |
| `DELETE` | `/api/v1/users/{id}/` | **Dual-write**: desactiva en Gateway DB + proxy DELETE a Artemisa |

### Clients — Proxy puro (requieren JWT + rol)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/v1/clients/` | Listar clientes. Filtro: `status`. Paginación: `page`, `page_size` |
| `POST` | `/api/v1/clients/` | Crear cliente. Campos: `company` (req), `email` (req), `phone`, `status` |
| `GET` | `/api/v1/clients/{id}/` | Obtener cliente por ID |
| `PUT` | `/api/v1/clients/{id}/` | Actualizar datos del cliente |
| `DELETE` | `/api/v1/clients/{id}/` | Soft delete → `status='inactive'` |

### Interactions — Proxy puro hacia Venus (requieren JWT + rol)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/v1/interactions/` | Listar interacciones (filtros, paginación) |
| `POST` | `/api/v1/interactions/` | Crear interacción |
| `GET` | `/api/v1/interactions/metrics/` | Métricas globales (totales + desglose por cliente) |
| `GET` | `/api/v1/interactions/follow-ups/{pending\|overdue}/` | Seguimientos pendientes o vencidos |
| `GET` | `/api/v1/interactions/client/{client_id}/` | Historial de interacciones de un cliente |
| `GET` | `/api/v1/interactions/client/{client_id}/summary/` | Resumen estadístico del cliente |
| `GET` | `/api/v1/interactions/{id}/` | Obtener interacción por ID |
| `PUT` | `/api/v1/interactions/{id}/` | Actualizar interacción |
| `DELETE` | `/api/v1/interactions/{id}/` | Eliminar interacción (soft delete) |
| `PATCH` | `/api/v1/interactions/{id}/close/` | Cerrar interacción |
| `GET` | `/api/v1/interactions/{id}/audit/` | Historial de cambios de una interacción |
| `POST` | `/api/v1/interactions/{id}/attachments/` | Subir adjunto (multipart proxy → Venus) |
| `GET` | `/api/v1/interactions/{id}/attachments/` | Listar adjuntos de una interacción |
| `GET` | `/api/v1/interactions/{id}/attachments/{att_id}/` | URL presignada de descarga |
| `DELETE` | `/api/v1/interactions/{id}/attachments/{att_id}/` | Eliminar adjunto (S3 + BD) |

### Health

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/v1/health/` | Estado del servicio |

---

## Permisos por rol

Tabla centralizada en `src/infrastructure/permissions/role_permissions.py`. **Un solo lugar para cambiar permisos:**

| Recurso | GET | POST | PUT | DELETE |
|---|---|---|---|---|
| **users** | admin, soporte | admin | admin | admin |
| **clients** | todos | admin, soporte | admin, soporte | admin |
| **interactions** | todos | admin, soporte | admin, soporte | admin |

> **Nota de visibilidad por rol (aplicada en los microservicios, no en el Gateway):**
> - **Admin/Soporte:** ven todas las interacciones.
> - **Comercial:** ve TODAS las interacciones de clientes donde tiene al menos una interacción propia ("clientes asignados"). Puede crear interacciones, pero solo puede editar/cerrar/subir adjuntos a sus propias. Follow-ups siempre son propios.
> - El Gateway solo verifica acceso al endpoint. El filtrado de datos se hace en Venus.

---

## Middleware stack

Cada request pasa por estos middlewares **en orden**:

```
Request del frontend
    │
    ▼
1. LoggingMiddleware      → Registra request entrante + response saliente (structlog JSON)
    │
    ▼
2. RateLimitMiddleware    → Limita: 5 req/min para /auth/login, 100 req/min para API
    │                       (por IP, en memoria — usar Redis en producción)
    │
    ▼
3. JWTMiddleware          → Valida Bearer token. Si no hay token o es inválido → 401
    │                       Rutas públicas: /auth/login, /health/, /docs/, /admin/
    │                       Verifica blacklist (tokens invalidados por logout)
    │                       Inyecta: request.user, request.auth_token
    │
    ▼
4. RolePermission (DRF)   → Verifica (método, recurso) contra ROUTE_PERMISSIONS
    │
    ▼
5. Vista DRF              → Ejecuta la lógica (auth o proxy)
```

---

## Excepciones de dominio

| Excepción | Código | HTTP | Cuándo |
|---|---|---|---|
| `InvalidCredentialsError` | `INVALID_CREDENTIALS` | 401 | Email o password incorrectos |
| `TokenExpiredError` | `TOKEN_EXPIRED` | 401 | JWT expiró |
| `TokenInvalidError` | `TOKEN_INVALID` | 401 | JWT malformado o firm inválida |
| `UnauthorizedError` | `UNAUTHORIZED` | 403 | Rol sin permiso para este recurso |
| `EmailAlreadyExistsError` | `EMAIL_ALREADY_EXISTS` | 409 | Email ya registrado |
| `UserNotFoundError` | `USER_NOT_FOUND` | 404 | No existe usuario con ese ID |
| `ServiceUnavailableError` | `SERVICE_UNAVAILABLE` | 503 | Microservicio interno no responde |

---

## Docker

### Levantar el servicio

```bash
# Opción 1: levantar todo el CRM con un solo comando (recomendado)
./startup.sh

# Opción 2: levantar solo Atenea
docker-compose up -d --build
```

### Comandos útiles

```bash
# Migraciones
docker-compose exec gateway python manage.py migrate

# Tests
docker-compose exec gateway python -m pytest tests/ -v

# Seed de usuarios (dual-write → mismos UUIDs en Atenea y Artemisa)
# ⚠️  Artemisa debe estar corriendo
docker-compose exec gateway python manage.py seed_users

# Seed de clientes (POST directo a Artemisa)
# ⚠️  Artemisa debe estar corriendo
docker-compose exec gateway python manage.py seed_clients

# Seed de interacciones (POST directo a Venus)
# ⚠️  Venus y Artemisa deben estar corriendo (necesita UUIDs de clientes y usuarios)
docker-compose exec gateway python manage.py seed_interactions

# Limpiar tokens expirados de la blacklist
docker-compose exec gateway python manage.py cleanup_blacklisted_tokens

# Logs
docker-compose logs -f gateway
```

### Usuarios seed

| Email | Password | Rol |
|---|---|---|
| admin@crm.com | Temporal123! | admin |
| soporte@crm.com | Temporal123! | soporte |
| comercial@crm.com | Temporal123! | comercial |

### Variables de entorno (`.env`)

```env
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=crm_gateway_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

JWT_SECRET_KEY=super-secret-jwt-key-min-32-bytes!
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_ALGORITHM=HS256

USERS_SERVICE_URL=http://users-service:8001/api/v1
INTERACTIONS_SERVICE_URL=http://interactions-service:8002

CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

RATE_LIMIT_LOGIN=5/minute
RATE_LIMIT_API=100/minute
```

### Red compartida

Ambos servicios comparten la red Docker `crm_network` para comunicación interna:

```bash
# Crear la red (una sola vez, startup.sh lo hace automáticamente)
docker network create crm_network
```

---

## Tests

**69 tests** — 0 failures, 0 warnings

```
tests/
├── conftest.py                          # Fixtures: usuarios por rol, tokens JWT, API clients
├── unit/
│   ├── test_login_use_case.py           #  5 tests — login: happy path, credenciales inválidas
│   ├── test_validate_token.py           #  5 tests — tokens válidos/expirados/malformados
│   └── test_create_user_gateway.py      #  6 tests — dual-write: happy path, rollback, UUID match
└── integration/
    ├── test_auth_endpoints.py           #  7 tests — login, logout, me via HTTP
    ├── test_gateway_proxy.py            # 13 tests — permisos, headers, proxy, tokens
    ├── test_dual_write.py               # 12 tests — create/update/delete con dual-write
    └── test_client_endpoints.py         # 21 tests — CRUD clientes, permisos, filtros
```

```bash
# Ejecutar tests localmente (sin Docker) — usa SQLite en memoria
python -m pytest tests/ -v --color=yes
```

---

## CORS (acceso desde el frontend)

`django-cors-headers` está configurado para permitir peticiones desde Vite (dev server del frontend Afrodita):

| Origen permitido (development) | Puerto |
|---|---|
| `http://localhost:5173` | Vite dev server |
| `http://127.0.0.1:5173` | Vite dev server |

Para agregar más orígenes en producción:
```env
CORS_ALLOWED_ORIGINS=https://mi-frontend.com,https://otro.com
```

---

## Script de inicio automático

`startup.sh` levanta **todo el sistema CRM** con un solo comando:

```bash
cd Atenea
./startup.sh               # Todo: build + migraciones + seed + tests
./startup.sh --skip-tests  # Sin tests
./startup.sh --help        # Ver opciones
```

El script ejecuta estos pasos en orden:

1. Limpia contenedores existentes
2. Crea la red Docker `crm_network`
3. Levanta Atenea (gateway) + aplica migraciones Django
4. Levanta Artemisa (users-service) + aplica migraciones Alembic
5. Espera a que Artemisa responda en `/api/v1/health/`
6. Levanta Venus (interactions-service) + aplica migraciones Alembic
7. Espera a que Venus responda en `/api/v1/health/`
8. Ejecuta `seed_users` (dual-write: mismo UUID en ambas BDs)
9. Ejecuta `seed_clients` (POST directo a Artemisa)
10. Ejecuta `seed_interactions` (POST directo a Venus)
11. Corre los tests de los tres servicios (opcional)

---

## Documentación API (Swagger)

| URL | Tipo |
|---|---|
| `/api/docs/` | Swagger UI (interactivo) |
| `/api/redoc/` | ReDoc |
| `/api/schema/` | Esquema OpenAPI JSON/YAML |
