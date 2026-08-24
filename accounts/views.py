from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import redirect, render

from .forms import CandidateRegisterForm, EmployerRegisterForm


def candidate_register(request):
    if request.user.is_authenticated:
        if hasattr(request.user, "candidate_profile"):
            return redirect("candidates:candidate_dashboard")
        elif hasattr(request.user, "employer_profile"):
            return redirect("dashboard:employer_dashboard")
        return redirect("home")

    form = CandidateRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        try:
            from services.firebase_service import sync_candidate_to_firestore
            sync_candidate_to_firestore(user, getattr(user, "candidate_profile", None))
        except Exception:
            pass
        login(request, user)
        messages.success(
            request,
            "Welcome! Your candidate account has been created. Complete your profile to get started.",
        )
        return redirect("candidates:candidate_dashboard")


    return render(request, "accounts/candidate_register.html", {"form": form})


def candidate_login(request):
    if request.user.is_authenticated:
        if hasattr(request.user, "candidate_profile"):
            return redirect("candidates:candidate_dashboard")
        elif hasattr(request.user, "employer_profile"):
            return redirect("dashboard:employer_dashboard")
        return redirect("home")

    error = None
    if request.method == "POST":
        identifier = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        # Look up user by username or email
        user_obj = User.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        ).first()

        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
        else:
            user = None

        if user is None:
            error = "Invalid credentials. Please verify your email/username and password."
        elif not hasattr(user, "candidate_profile"):
            error = "This account is not registered as a candidate. Please use employer login."
        else:
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            next_url = request.GET.get("next")
            if next_url:
                return redirect(next_url)
            return redirect("candidates:candidate_dashboard")

    return render(
        request,
        "accounts/candidate_login.html",
        {"error": error, "username": request.POST.get("username", "")},
    )


def employer_register(request):
    if request.user.is_authenticated:
        if hasattr(request.user, "employer_profile"):
            return redirect("dashboard:employer_dashboard")
        elif hasattr(request.user, "candidate_profile"):
            return redirect("candidates:candidate_dashboard")
        return redirect("home")

    form = EmployerRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        try:
            from services.firebase_service import sync_employer_to_firestore
            sync_employer_to_firestore(user, getattr(user, "employer_profile", None))
        except Exception:
            pass
        login(request, user)
        messages.success(
            request,
            "Welcome! Your employer account has been created.",
        )
        return redirect("dashboard:employer_dashboard")


    return render(request, "accounts/employer_register.html", {"form": form})


def employer_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect("dashboard:admin_dashboard")
        elif hasattr(request.user, "employer_profile"):
            return redirect("dashboard:employer_dashboard")
        elif hasattr(request.user, "candidate_profile"):
            return redirect("candidates:candidate_dashboard")
        return redirect("home")

    error = None
    if request.method == "POST":
        identifier = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user_obj = User.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        ).first()

        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
        else:
            user = None

        if user is None:
            error = "Invalid credentials. Please verify your email/username and password."
        elif user.is_staff or user.is_superuser:
            login(request, user)
            messages.success(request, f"Welcome back, Administrator {user.first_name or user.username}!")
            next_url = request.GET.get("next")
            if next_url:
                return redirect(next_url)
            return redirect("dashboard:admin_dashboard")
        elif not hasattr(user, "employer_profile"):
            error = "This account is not registered as an employer. Please use candidate login."
        else:
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            next_url = request.GET.get("next")
            if next_url:
                return redirect(next_url)
            return redirect("dashboard:employer_dashboard")

    return render(
        request,
        "accounts/employer_login.html",
        {"error": error, "username": request.POST.get("username", "")},
    )


def logout_view(request):
    """Single logout endpoint shared by both roles."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")
