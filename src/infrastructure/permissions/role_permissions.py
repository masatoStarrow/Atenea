"""
Centralized role permissions table.
Single source of truth for all route-level permissions.
"""

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    SOPORTE = "soporte"
    COMERCIAL = "comercial"


ALL_ROLES = [Role.ADMIN, Role.SOPORTE, Role.COMERCIAL]

# ── ÚNICA FUENTE DE VERDAD DE PERMISOS ────────────────────────────────────
# Formato: (método HTTP, recurso) → roles permitidos
# Para cambiar un permiso: solo modificar esta tabla, nada más.
ROUTE_PERMISSIONS: dict[tuple, list[Role]] = {
    # ── Usuarios ──────────────────────────────────────────────────
    ("GET", "users"): ALL_ROLES,
    ("POST", "users"): [Role.ADMIN],
    ("PUT", "users"): [Role.ADMIN],
    ("DELETE", "users"): [Role.ADMIN],
    # ── Clientes ──────────────────────────────────────────────────
    ("GET", "clients"): ALL_ROLES,
    ("POST", "clients"): [Role.ADMIN, Role.SOPORTE],
    ("PUT", "clients"): [Role.ADMIN, Role.SOPORTE],
    ("DELETE", "clients"): [Role.ADMIN],
    # ── Interacciones ─────────────────────────────────────────────
    ("GET", "interactions"): ALL_ROLES,
    ("POST", "interactions"): ALL_ROLES,
    ("PUT", "interactions"): ALL_ROLES,
    ("PATCH", "interactions"): ALL_ROLES,
    ("DELETE", "interactions"): [Role.ADMIN],
}
