"""Service-to-service authentication for HumanDB Recruitment integration.

Secured via header:
    X-HumanDB-Integration-Key: <secret>
Configured via environment variable:
    HUMANDB_INTEGRATION_API_KEY
"""

import hmac
import os
from django.conf import settings
from rest_framework import authentication, exceptions, permissions


class HumanDBServiceUser:
    """Lightweight user object representing the authenticated HumanDB recruitment service."""

    is_authenticated = True
    is_active = True
    is_anonymous = False
    is_staff = False
    is_superuser = False
    username = "humandb_integration_service"
    pk = None
    id = None

    def __str__(self) -> str:
        return "HumanDB Integration Service"


class HumanDBIntegrationAuthentication(authentication.BaseAuthentication):
    """Authenticate incoming HTTP requests using the X-HumanDB-Integration-Key header."""

    HEADER_NAME = "HTTP_X_HUMANDB_INTEGRATION_KEY"

    def authenticate(self, request):
        auth_key = None
        if hasattr(request, "headers"):
            auth_key = request.headers.get("X-HumanDB-Integration-Key")
        if not auth_key:
            auth_key = request.META.get(self.HEADER_NAME)

        if not auth_key:
            raise exceptions.AuthenticationFailed(
                detail="Missing required header 'X-HumanDB-Integration-Key'."
            )

        expected_key = getattr(
            settings,
            "HUMANDB_INTEGRATION_API_KEY",
            os.getenv("HUMANDB_INTEGRATION_API_KEY", ""),
        )

        if not expected_key or not expected_key.strip():
            raise exceptions.AuthenticationFailed(
                detail="HUMANDB_INTEGRATION_API_KEY is not configured on the server."
            )

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(
            str(auth_key).strip().encode("utf-8"),
            str(expected_key).strip().encode("utf-8"),
        ):
            raise exceptions.AuthenticationFailed(
                detail="Invalid 'X-HumanDB-Integration-Key' provided."
            )

        return (HumanDBServiceUser(), str(auth_key).strip())

    def authenticate_header(self, request):
        return 'X-HumanDB-Integration-Key realm="HumanDB Integration"'


class HasHumanDBIntegrationKey(permissions.BasePermission):
    """Ensures request is strictly authenticated via HumanDBIntegrationAuthentication."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and getattr(request.user, "is_authenticated", False)
            and getattr(request.user, "username", "") == "humandb_integration_service"
        )
