"""
URL configuration for auth endpoints.
"""

from django.urls import path

from src.adapters.inbound.http.auth.views import LoginView, LogoutView, MeView

urlpatterns = [
    path('login', LoginView.as_view(), name='auth-login'),
    path('logout', LogoutView.as_view(), name='auth-logout'),
    path('me', MeView.as_view(), name='auth-me'),
]
