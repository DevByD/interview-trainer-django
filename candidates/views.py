from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render

from accounts.decorators import candidate_required
from assessments.models import Assessment

from .forms import CandidateProfileForm


@candidate_required
def dashboard(request):
    profile = request.user.candidate_profile
    assessments = (
        Assessment.objects.filter(candidate=request.user)
        .select_related("employer", "result")
        .order_by("-created_at")
    )
    context = {
        "profile": profile,
        "completion_percentage": profile.completion_percentage,
        "assessments": assessments,
        "upcoming_count": assessments.filter(status=Assessment.Status.PENDING).count(),
        "ongoing_count": assessments.filter(status=Assessment.Status.ONGOING).count(),
        "completed_count": assessments.filter(status=Assessment.Status.COMPLETED).count(),
        "missed_count": assessments.filter(
            Q(status=Assessment.Status.EXPIRED)
            | Q(candidate_status=Assessment.CandidateStatus.NOT_ATTENDED)
        ).count(),
    }
    return render(request, "candidates/dashboard.html", context)


@candidate_required
def profile(request):
    prof = request.user.candidate_profile
    form = CandidateProfileForm(
        request.POST or None, request.FILES or None, instance=prof
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("candidates:candidate_profile")

    return render(
        request,
        "candidates/profile.html",
        {
            "form": form,
            "profile": prof,
            "completion_percentage": prof.completion_percentage,
        },
    )
