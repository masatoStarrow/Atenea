"""
Gateway proxy views — forwards requests to internal microservices.
Users: dual-write (gateway DB + users-service).
Interactions / Clients: pure proxy.
"""

import asyncio
import json

import structlog
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

from src.adapters.inbound.http.auth.serializers import (
    SuccessResponseSerializer,
    ErrorResponseSerializer,
)
from src.adapters.inbound.http.gateway.serializers import (
    CreateUserProxySerializer,
    UpdateUserProxySerializer,
    CreateClientProxySerializer,
    UpdateClientProxySerializer,
    CreateInteractionProxySerializer,
    UpdateInteractionProxySerializer,
)
from src.infrastructure.permissions.role_permission import RolePermission
from src.adapters.outbound.http_client.users_client import UsersServiceClient
from src.adapters.outbound.http_client.interactions_client import InteractionsServiceClient
from src.adapters.outbound.persistence.django_user_repository import DjangoUserRepository
from src.application.use_cases.create_user_gateway import CreateUserGateway
from src.domain.exceptions import (
    ServiceUnavailableError,
    EmailAlreadyExistsError,
)

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ── helpers ──────────────────────────────────────────────────────────────

def _error_response(code: str, message: str, http_status: int) -> Response:
    return Response(
        {"success": False, "error": {"code": code, "message": message}},
        status=http_status,
    )


class UserProxyView(APIView):
    """
    Proxy for /api/v1/users/ → users-service.
    POST / PUT / DELETE implement dual-write (gateway DB + users-service).
    GET is pure proxy.
    """
    permission_classes = [RolePermission]

    # ── GET — pure proxy ─────────────────────────────────────────────────

    @extend_schema(
        summary="Listar usuarios",
        description="Proxy hacia users-service GET /users/",
        responses={200: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Users (Proxy)"],
    )
    def get(self, request: Request, user_id=None) -> Response:
        return self._proxy(request, 'GET', user_id)

    # ── POST — dual-write create ─────────────────────────────────────────

    @extend_schema(
        summary="Crear usuario",
        description=(
            "Dual-write: crea el usuario en el Gateway DB (con contraseña) "
            "y en el users-service (sin contraseña). Ambos comparten UUID."
        ),
        request=CreateUserProxySerializer,
        responses={201: SuccessResponseSerializer, 409: ErrorResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Users (Proxy)"],
    )
    def post(self, request: Request) -> Response:
        serializer = CreateUserProxySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        repo = DjangoUserRepository()
        client = UsersServiceClient()
        use_case = CreateUserGateway(
            user_repository=repo,
            users_client=client,
            async_runner=_run_async,
        )

        try:
            result = use_case.execute(
                email=data["email"],
                full_name=data["full_name"],
                role=data["role"],
                password=data["password"],
                request_user_id=str(request.user.id) if hasattr(request.user, "id") else None,
                request_user_role=getattr(request.user, "role", None),
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except EmailAlreadyExistsError as e:
            return _error_response(e.code, e.message, status.HTTP_409_CONFLICT)
        except ServiceUnavailableError as e:
            return _error_response(e.code, e.message, status.HTTP_503_SERVICE_UNAVAILABLE)

    # ── PUT — dual-write update ──────────────────────────────────────────

    @extend_schema(
        summary="Actualizar usuario",
        description=(
            "Dual-write: actualiza el usuario en el Gateway DB "
            "y en el users-service."
        ),
        request=UpdateUserProxySerializer,
        responses={200: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Users (Proxy)"],
    )
    def put(self, request: Request, user_id=None) -> Response:
        if not user_id:
            return _error_response("VALIDATION_ERROR", "user_id es requerido", status.HTTP_400_BAD_REQUEST)

        serializer = UpdateUserProxySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        repo = DjangoUserRepository()
        client = UsersServiceClient()

        # 1. Update gateway DB
        try:
            repo.update(
                user_id,
                full_name=data.get("full_name"),
                role=data.get("role"),
                is_active=data.get("is_active"),
            )
        except ValueError:
            logger.warning("user_not_found_in_gateway_for_update", user_id=user_id)
            # Continue with proxy even if user doesn't exist locally

        # 2. Proxy PUT to users-service
        try:
            response = _run_async(
                client.forward_request(
                    method="PUT",
                    path=f"/users/{user_id}",
                    body=json.dumps(request.data).encode(),
                    query_params=request.query_params.dict() if request.query_params else None,
                    user_id=str(request.user.id) if hasattr(request.user, "id") else None,
                    user_role=getattr(request.user, "role", None),
                )
            )
            try:
                resp_data = response.json()
            except Exception:
                resp_data = response.text
            return Response(resp_data, status=response.status_code)
        except ServiceUnavailableError as e:
            return _error_response(e.code, e.message, status.HTTP_503_SERVICE_UNAVAILABLE)

    # ── DELETE — dual-write deactivate ───────────────────────────────────

    @extend_schema(
        summary="Eliminar usuario",
        description=(
            "Dual-write: desactiva el usuario en el Gateway DB "
            "y elimina/desactiva en el users-service."
        ),
        responses={200: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Users (Proxy)"],
    )
    def delete(self, request: Request, user_id=None) -> Response:
        if not user_id:
            return _error_response("VALIDATION_ERROR", "user_id es requerido", status.HTTP_400_BAD_REQUEST)

        repo = DjangoUserRepository()
        client = UsersServiceClient()

        # 1. Deactivate in gateway DB
        repo.deactivate(user_id)

        # 2. Proxy DELETE to users-service
        try:
            response = _run_async(
                client.forward_request(
                    method="DELETE",
                    path=f"/users/{user_id}",
                    user_id=str(request.user.id) if hasattr(request.user, "id") else None,
                    user_role=getattr(request.user, "role", None),
                )
            )
            try:
                resp_data = response.json()
            except Exception:
                resp_data = response.text
            return Response(resp_data, status=response.status_code)
        except ServiceUnavailableError as e:
            return _error_response(e.code, e.message, status.HTTP_503_SERVICE_UNAVAILABLE)

    # ── Pure proxy (only used by GET now) ────────────────────────────────

    def _proxy(self, request: Request, method: str, user_id=None) -> Response:
        client = UsersServiceClient()
        path = '/users'
        if user_id:
            path = f'/users/{user_id}'

        try:
            response = _run_async(
                client.forward_request(
                    method=method,
                    path=path,
                    body=request.body if method in ('POST', 'PUT', 'PATCH') else None,
                    query_params=request.query_params.dict() if request.query_params else None,
                    user_id=str(request.user.id) if hasattr(request.user, 'id') else None,
                    user_role=getattr(request.user, 'role', None),
                )
            )
            try:
                data = response.json()
            except Exception:
                data = response.text

            return Response(data, status=response.status_code)
        except ServiceUnavailableError as e:
            return _error_response(e.code, e.message, status.HTTP_503_SERVICE_UNAVAILABLE)


class ClientProxyView(APIView):
    """
    Proxy for /api/v1/clients/ → users-service.
    Pure proxy — no dual-write.
    POST/PUT serialize validated_data to avoid RawPostDataException.
    """
    permission_classes = [RolePermission]

    @extend_schema(
        summary="Listar clientes",
        description="Proxy hacia users-service GET /clients/",
        responses={200: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Clients (Proxy)"],
    )
    def get(self, request: Request, client_id=None) -> Response:
        return self._proxy(request, 'GET', client_id)

    @extend_schema(
        summary="Crear cliente",
        description="Proxy hacia users-service POST /clients/",
        request=CreateClientProxySerializer,
        responses={201: SuccessResponseSerializer, 409: ErrorResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Clients (Proxy)"],
    )
    def post(self, request: Request) -> Response:
        serializer = CreateClientProxySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        body = json.dumps(serializer.validated_data).encode()
        return self._proxy(request, 'POST', body=body)

    @extend_schema(
        summary="Actualizar cliente",
        description="Proxy hacia users-service PUT /clients/{id}/",
        request=UpdateClientProxySerializer,
        responses={200: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Clients (Proxy)"],
    )
    def put(self, request: Request, client_id=None) -> Response:
        serializer = UpdateClientProxySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": serializer.errors}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        body = json.dumps(serializer.validated_data).encode()
        return self._proxy(request, 'PUT', client_id, body=body)

    @extend_schema(
        summary="Desactivar cliente",
        description="Proxy hacia users-service DELETE /clients/{id}/ (soft delete → inactive).",
        responses={200: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Clients (Proxy)"],
    )
    def delete(self, request: Request, client_id=None) -> Response:
        return self._proxy(request, 'DELETE', client_id)

    def _proxy(self, request: Request, method: str, client_id=None, body: bytes | None = None) -> Response:
        client = UsersServiceClient()
        path = '/clients'
        if client_id:
            path = f'/clients/{client_id}'

        if body is None and method in ('POST', 'PUT', 'PATCH'):
            body = request.body

        try:
            response = _run_async(
                client.forward_request(
                    method=method,
                    path=path,
                    body=body,
                    query_params=request.query_params.dict() if request.query_params else None,
                    user_id=str(request.user.id) if hasattr(request.user, 'id') else None,
                    user_role=getattr(request.user, 'role', None),
                )
            )
            try:
                data = response.json()
            except Exception:
                data = response.text

            return Response(data, status=response.status_code)
        except ServiceUnavailableError as e:
            return _error_response(e.code, e.message, status.HTTP_503_SERVICE_UNAVAILABLE)


class InteractionProxyView(APIView):
    """Proxy for /api/v1/interactions/ → interactions-service."""
    permission_classes = [RolePermission]

    @extend_schema(
        summary="Listar interacciones",
        description="Proxy hacia interactions-service GET /interactions/",
        responses={200: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Interactions (Proxy)"],
    )
    def get(self, request: Request, interaction_id=None) -> Response:
        return self._proxy(request, 'GET', interaction_id)

    @extend_schema(
        summary="Crear interacción",
        description="Proxy hacia interactions-service POST /interactions/",
        request=CreateInteractionProxySerializer,
        responses={201: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Interactions (Proxy)"],
    )
    def post(self, request: Request) -> Response:
        return self._proxy(request, 'POST')

    @extend_schema(
        summary="Actualizar interacción",
        description="Proxy hacia interactions-service PUT /interactions/{id}/",
        request=UpdateInteractionProxySerializer,
        responses={200: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Interactions (Proxy)"],
    )
    def put(self, request: Request, interaction_id=None) -> Response:
        return self._proxy(request, 'PUT', interaction_id)

    @extend_schema(
        summary="Eliminar interacción",
        description="Proxy hacia interactions-service DELETE /interactions/{id}/",
        responses={200: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Interactions (Proxy)"],
    )
    def delete(self, request: Request, interaction_id=None) -> Response:
        return self._proxy(request, 'DELETE', interaction_id)

    def _proxy(self, request: Request, method: str, interaction_id=None) -> Response:
        client = InteractionsServiceClient()
        path = '/interactions'
        if interaction_id:
            path = f'/interactions/{interaction_id}'

        try:
            response = _run_async(
                client.forward_request(
                    method=method,
                    path=path,
                    body=request.body if method in ('POST', 'PUT', 'PATCH') else None,
                    query_params=request.query_params.dict() if request.query_params else None,
                    user_id=str(request.user.id) if hasattr(request.user, 'id') else None,
                    user_role=getattr(request.user, 'role', None),
                )
            )
            try:
                data = response.json()
            except Exception:
                data = response.text

            return Response(data, status=response.status_code)
        except ServiceUnavailableError as e:
            return _error_response(e.code, e.message, status.HTTP_503_SERVICE_UNAVAILABLE)


class InteractionByClientProxyView(APIView):
    """Proxy for /api/v1/interactions/client/{client_id}/ → interactions-service."""
    permission_classes = [RolePermission]

    @extend_schema(
        summary="Listar interacciones por cliente",
        description="Proxy hacia interactions-service GET /interactions/client/{client_id}/",
        responses={200: SuccessResponseSerializer, 503: ErrorResponseSerializer},
        tags=["Interactions (Proxy)"],
    )
    def get(self, request: Request, client_id=None) -> Response:
        client = InteractionsServiceClient()
        path = f'/interactions/client/{client_id}'

        try:
            response = _run_async(
                client.forward_request(
                    method='GET',
                    path=path,
                    query_params=request.query_params.dict() if request.query_params else None,
                    user_id=str(request.user.id) if hasattr(request.user, 'id') else None,
                    user_role=getattr(request.user, 'role', None),
                )
            )
            try:
                data = response.json()
            except Exception:
                data = response.text

            return Response(data, status=response.status_code)
        except ServiceUnavailableError as e:
            return _error_response(e.code, e.message, status.HTTP_503_SERVICE_UNAVAILABLE)
