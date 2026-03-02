"""
DRF Authentication class that reads the user set by JWTMiddleware.
"""

from rest_framework.authentication import BaseAuthentication


class JWTAuthentication(BaseAuthentication):
    """
    DRF authentication backend that trusts the JWTMiddleware.
    The middleware has already validated the token and set request.user.
    This class bridges that into DRF's authentication system.
    """

    def authenticate(self, request):
        # The JWTMiddleware sets user on the Django request
        django_request = request._request if hasattr(request, '_request') else request
        user = getattr(django_request, 'user', None)

        if user and hasattr(user, 'id') and hasattr(user, 'role'):
            token = getattr(django_request, 'auth_token', None)
            return (user, token)

        return None
