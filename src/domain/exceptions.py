"""
Domain exceptions — pure Python, no framework dependencies.
"""


class DomainException(Exception):
    """Base class for domain exceptions."""
    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class InvalidCredentialsError(DomainException):
    """Raised when login credentials are incorrect."""
    def __init__(self, message: str = "Email o contraseña incorrectos"):
        super().__init__(message=message, code="INVALID_CREDENTIALS")


class TokenExpiredError(DomainException):
    """Raised when a JWT token has expired."""
    def __init__(self, message: str = "Token expirado"):
        super().__init__(message=message, code="TOKEN_EXPIRED")


class TokenInvalidError(DomainException):
    """Raised when a JWT token is malformed or invalid."""
    def __init__(self, message: str = "Token inválido"):
        super().__init__(message=message, code="TOKEN_INVALID")


class UnauthorizedError(DomainException):
    """Raised when a user doesn't have the required permissions."""
    def __init__(self, message: str = "No tiene permisos para acceder a este recurso"):
        super().__init__(message=message, code="UNAUTHORIZED")


class ServiceUnavailableError(DomainException):
    """Raised when an internal microservice is not reachable."""
    def __init__(self, message: str = "Servicio no disponible"):
        super().__init__(message=message, code="SERVICE_UNAVAILABLE")


class EmailAlreadyExistsError(DomainException):
    """Raised when a user with the given email already exists."""
    def __init__(self, message: str = "Ya existe un usuario con ese email"):
        super().__init__(message=message, code="EMAIL_ALREADY_EXISTS")


class UserNotFoundError(DomainException):
    """Raised when a user is not found."""
    def __init__(self, message: str = "Usuario no encontrado"):
        super().__init__(message=message, code="USER_NOT_FOUND")
