"""
DRF Permission class that checks the centralized ROUTE_PERMISSIONS table.
"""

from rest_framework.permissions import BasePermission

from src.infrastructure.permissions.role_permissions import ROUTE_PERMISSIONS


class RolePermission(BasePermission):
    """
    Consulta ROUTE_PERMISSIONS para decidir si el rol del usuario
    tiene acceso al recurso solicitado.
    Si la ruta no está en la tabla → deniega por defecto (fail-safe).
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not hasattr(user, 'role'):
            return False

        resource = self._extract_resource(request.path)
        allowed_roles = ROUTE_PERMISSIONS.get((request.method, resource))

        if allowed_roles is None:
            return False  # Ruta no registrada → denegar

        return user.role in [r.value if hasattr(r, 'value') else r for r in allowed_roles]

    @staticmethod
    def _extract_resource(path: str) -> str:
        """
        Extract the resource name from the URL path.
        /api/v1/users/          → 'users'
        /api/v1/interactions/5/ → 'interactions'
        """
        parts = [p for p in path.split('/') if p]
        for i, part in enumerate(parts):
            if part.startswith('v') and part[1:].isdigit():
                if i + 1 < len(parts):
                    return parts[i + 1]
        return ''
