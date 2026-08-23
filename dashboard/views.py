from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import employer_required
from accounts.models import CandidateProfile
from assessments.models import Assessment


def home(request):
    """Public landing page."""
    if request.user.is_authenticated:
        if hasattr(request.user, "candidate_profile"):
            return redirect("candidates:candidate_dashboard")
        elif hasattr(request.user, "employer_profile"):
            return redirect("dashboard:employer_dashboard")

    from assessments.models import Question, CodingQuestion, Assessment

    total_candidates = CandidateProfile.objects.count()
    total_assessments = Assessment.objects.count()
    total_questions = Question.objects.count()
    total_coding_problems = CodingQuestion.objects.count()

    context = {
        "stat_candidates": total_candidates,
        "stat_assessments": total_assessments,
        "stat_questions": total_questions,
        "stat_coding_problems": total_coding_problems,
    }
    return render(request, "home.html", context)



@employer_required
def employer_dashboard(request):
    """Main dashboard for recruiters & hiring managers."""
    employer_assessments = (
        Assessment.objects.filter(employer=request.user)
        .select_related("candidate", "result")
        .order_by("-created_at")
    )

    total_candidates = CandidateProfile.objects.count()
    active_tests = employer_assessments.filter(
        status__in=[Assessment.Status.PENDING, Assessment.Status.ONGOING]
    ).count()
    completed_tests = employer_assessments.filter(
        status=Assessment.Status.COMPLETED
    ).count()
    missed_tests = employer_assessments.filter(
        Q(status=Assessment.Status.EXPIRED)
        | Q(candidate_status=Assessment.CandidateStatus.NOT_ATTENDED)
    ).count()

    recent_assessments = employer_assessments[:10]

    context = {
        "employer_profile": getattr(request.user, "employer_profile", None),
        "total_candidates": total_candidates,
        "active_tests": active_tests,
        "completed_tests": completed_tests,
        "missed_tests": missed_tests,
        "recent_assessments": recent_assessments,
    }
    return render(request, "dashboard/employer_dashboard.html", context)


@employer_required
def employer_candidates_list(request):
    """Directory of all registered candidates."""
    query = request.GET.get("q", "").strip()
    candidates = CandidateProfile.objects.select_related("user").order_by("-created_at")

    if query:
        candidates = candidates.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(user__username__icontains=query)
            | Q(skills__icontains=query)
            | Q(education__icontains=query)
        )

    context = {
        "candidates": candidates,
        "query": query,
        "total_count": candidates.count(),
    }
    return render(request, "dashboard/employer_candidates.html", context)


@employer_required
def employer_candidate_detail(request, candidate_id):
    """Detailed profile view of a specific candidate for employers."""
    candidate_profile = get_object_or_404(
        CandidateProfile.objects.select_related("user"), pk=candidate_id
    )

    # Assessments assigned specifically by this employer to this candidate
    assigned_assessments = (
        Assessment.objects.filter(
            employer=request.user, candidate=candidate_profile.user
        )
        .select_related("result")
        .order_by("-created_at")
    )

    context = {
        "candidate": candidate_profile,
        "completion_percentage": candidate_profile.completion_percentage,
        "assigned_assessments": assigned_assessments,
    }
    return render(request, "dashboard/employer_candidate_detail.html", context)


def error_400_view(request, exception=None):
    """Custom 400 bad request error page."""
    return render(request, "400.html", status=400)


def error_404_view(request, exception=None):
    """Custom 404 error page."""
    return render(request, "404.html", status=404)



def error_403_view(request, exception=None):
    """Custom 403 forbidden error page."""
    return render(request, "403.html", status=403)


def error_500_view(request):
    """Custom 500 server error page."""
    return render(request, "500.html", status=500)

