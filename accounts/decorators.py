"""Reusable view decorators for role-based access control."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect


def _role_required(profile_attr: str, login_url_name: str):
    """Factory that builds a decorator enforcing one specific role."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url=f"accounts:{login_url_name}")

            profile = getattr(request.user, profile_attr, None)
            if profile is None:
                messages.error(
                    request,
                    "You do not have permission to access that page.",
                )
                return redirect("home")
            return view_func(request, *args, **kwargs)

        return _wrapped

    decorator.login_url_name = login_url_name
    return decorator


def candidate_required(view_func):
    """Allow only authenticated users that own a CandidateProfile."""
    return _role_required("candidate_profile", "candidate_login")(view_func)


def employer_required(view_func):
    """Allow only authenticated users that own an EmployerProfile."""
    return _role_required("employer_profile", "employer_login")(view_func)


def admin_required(view_func):
    """Allow only authenticated users who are staff or superusers."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="accounts:employer_login")
        if not (request.user.is_staff or request.user.is_superuser):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("You do not have administrative permission to access this area.")
        return view_func(request, *args, **kwargs)
    return _wrapped
