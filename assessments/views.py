"""Views for employer assessment management and candidate test taking."""

import json
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import candidate_required, employer_required
from accounts.models import CandidateProfile
from assessments.email_service import send_assessment_invitation
from assessments.forms import AssessmentCreateForm
from assessments.models import Answer, Assessment, AssessmentQuestion, Question
from assessments.services import expire_past_due_assessments, grade_and_complete_assessment



# ---------------------------------------------------------------------------
# Employer Assessment Views
# ---------------------------------------------------------------------------

@employer_required
def employer_assessment_create(request):
    """Create and configure a new assessment for a registered candidate."""
    initial_cand_id = request.GET.get("candidate_id")
    initial_user = None
    if initial_cand_id:
        try:
            cand_profile = CandidateProfile.objects.select_related("user").get(pk=initial_cand_id)
            initial_user = cand_profile.user
        except CandidateProfile.DoesNotExist:
            pass

    # Provide question bank totals for the interactive UI counters
    logical_bank_count = Question.objects.filter(section=Question.Sections.LOGICAL).count()
    quant_bank_count = Question.objects.filter(section=Question.Sections.QUANTITATIVE).count()
    tech_bank_count = Question.objects.filter(section=Question.Sections.TECHNICAL).count()

    form = AssessmentCreateForm(
        request.POST or None,
        initial_candidate=initial_user,
    )

    # Candidate profile data for JS live preview
    candidate_profiles_qs = CandidateProfile.objects.select_related("user").all()
    candidates_meta = {}
    for cp in candidate_profiles_qs:
        candidates_meta[str(cp.user_id)] = {
            "name": cp.user.get_full_name() or cp.user.username,
            "email": cp.user.email,
            "phone": cp.phone or "Not specified",
            "education": cp.education or "Not specified",
            "skills": cp.skills or "Not specified",
            "completed": cp.profile_completed,
            "percentage": cp.completion_percentage,
        }

    if request.method == "POST" and form.is_valid():
        candidate_user = form.cleaned_data["candidate"]
        title = form.cleaned_data["title"]
        start_datetime = form.cleaned_data["start_datetime"]
        expire_datetime = form.cleaned_data["expire_datetime"]
        duration_minutes = form.cleaned_data["duration_minutes"]
        sections = form.cleaned_data["sections"]
        logical_count = form.cleaned_data.get("logical_count") or 0
        quant_count = form.cleaned_data.get("quant_count") or 0
        technical_count = form.cleaned_data.get("technical_count") or 0

        # Create Assessment instance
        assessment = Assessment.objects.create(
            employer=request.user,
            candidate=candidate_user,
            title=title,
            start_time=start_datetime,
            expire_time=expire_datetime,
            duration_minutes=duration_minutes,
            status=Assessment.Status.PENDING,
            candidate_status=Assessment.CandidateStatus.NOT_STARTED,
        )

        # Assign questions in order
        order_index = 1
        questions_to_link = []

        if "LOGICAL" in sections and logical_count > 0:
            qs = Question.objects.filter(section=Question.Sections.LOGICAL).order_by("id")[:logical_count]
            for q in qs:
                questions_to_link.append(AssessmentQuestion(assessment=assessment, question=q, order=order_index))
                order_index += 1

        if "QUANTITATIVE" in sections and quant_count > 0:
            qs = Question.objects.filter(section=Question.Sections.QUANTITATIVE).order_by("id")[:quant_count]
            for q in qs:
                questions_to_link.append(AssessmentQuestion(assessment=assessment, question=q, order=order_index))
                order_index += 1

        if "TECHNICAL" in sections and technical_count > 0:
            qs = Question.objects.filter(section=Question.Sections.TECHNICAL).order_by("id")[:technical_count]
            for q in qs:
                questions_to_link.append(AssessmentQuestion(assessment=assessment, question=q, order=order_index))
                order_index += 1

        AssessmentQuestion.objects.bulk_create(questions_to_link)

        # Dispatch email invitation
        email_sent = send_assessment_invitation(assessment, request=request)

        cand_name = candidate_user.get_full_name() or candidate_user.username
        if email_sent:
            messages.success(
                request,
                f"Assessment '{title}' created and invitation email delivered to {cand_name}.",
            )
        else:
            messages.success(
                request,
                f"Assessment '{title}' created successfully for {cand_name}. Test link generated.",
            )

        return redirect("assessments:employer_assessment_list")

    context = {
        "form": form,
        "logical_bank_count": logical_bank_count,
        "quant_bank_count": quant_bank_count,
        "tech_bank_count": tech_bank_count,
        "candidates_meta_json": json.dumps(candidates_meta),
    }
    return render(request, "assessments/create_assessment.html", context)


@employer_required
def employer_assessment_list(request):
    """List all assessments created by this employer."""
    assessments = (
        Assessment.objects.filter(employer=request.user)
        .select_related("candidate", "result")
        .order_by("-created_at")
    )
    context = {
        "assessments": assessments,
        "total_count": assessments.count(),
    }
    return render(request, "assessments/employer_assessment_list.html", context)


# ---------------------------------------------------------------------------
# Candidate Secure Test Entry & Taking Views
# ---------------------------------------------------------------------------

def test_entry(request, token):
    """Secure test portal entry by token."""
    # 1. Require authentication
    if not request.user.is_authenticated:
        return redirect(f"/candidate/login/?next=/test/{token}/")

    # 2. Require candidate role
    if not hasattr(request.user, "candidate_profile"):
        messages.error(request, "Only registered candidates can access assessments.")
        return render(
            request,
            "assessments/test_gate.html",
            {"gate_type": "wrong_role"},
            status=403,
        )

    # 3. Retrieve assessment
    assessment = get_object_or_404(
        Assessment.objects.select_related("employer", "employer__employer_profile"),
        token=token,
    )

    # 4. Enforce candidate ownership
    if assessment.candidate != request.user:
        return render(
            request,
            "assessments/test_gate.html",
            {"gate_type": "unauthorized", "assessment": assessment},
            status=403,
        )

    now = timezone.now()

    # 5. Check if already completed
    if assessment.status == Assessment.Status.COMPLETED:
        return render(
            request,
            "assessments/test_gate.html",
            {"gate_type": "completed", "assessment": assessment},
        )

    # 6. Check if expired or missed
    if assessment.status == Assessment.Status.EXPIRED or assessment.candidate_status == Assessment.CandidateStatus.NOT_ATTENDED:
        return render(
            request,
            "assessments/test_gate.html",
            {"gate_type": "expired", "assessment": assessment},
        )

    # 7. Check if current time is past expiry
    if now > assessment.expire_time:
        assessment.status = Assessment.Status.EXPIRED
        assessment.candidate_status = Assessment.CandidateStatus.NOT_ATTENDED
        assessment.save(update_fields=["status", "candidate_status", "updated_at"])
        return render(
            request,
            "assessments/test_gate.html",
            {"gate_type": "expired", "assessment": assessment},
        )

    # 8. Check if scheduled window has not opened yet
    if now < assessment.start_time:
        return render(
            request,
            "assessments/test_gate.html",
            {"gate_type": "not_started", "assessment": assessment},
        )

    # 9. If PENDING, show instructions page
    if assessment.status == Assessment.Status.PENDING:
        questions_qs = assessment.questions.select_related("question").all()
        sections_found = set(q.question.get_section_display() for q in questions_qs)
        return render(
            request,
            "assessments/test_instructions.html",
            {
                "assessment": assessment,
                "sections_display": ", ".join(sorted(sections_found)),
                "question_count": questions_qs.count(),
            },
        )

    # 10. If ONGOING, render interactive assessment taking interface
    if assessment.status == Assessment.Status.ONGOING:
        # Check deadline
        deadline = assessment.deadline
        remaining_seconds = max(0, int((deadline - now).total_seconds()))

        if remaining_seconds <= 0:
            # Time has run out, auto grade whatever has been submitted
            existing_answers = {
                ans.question_id: ans.selected_answer
                for ans in Answer.objects.filter(assessment=assessment)
            }
            result = grade_and_complete_assessment(assessment, existing_answers)
            messages.info(request, "Assessment time expired. Your test has been submitted.")
            return redirect("results:candidate_result", result_id=result.id)

        assessment_questions = (
            assessment.questions.select_related("question")
            .order_by("order", "id")
        )

        saved_answers = {
            ans.question_id: ans.selected_answer
            for ans in Answer.objects.filter(assessment=assessment)
        }

        # Format questions for the template (NEVER EXPOSE correct_answer)
        questions_data = []
        for index, aq in enumerate(assessment_questions, start=1):
            q = aq.question
            questions_data.append({
                "number": index,
                "id": q.id,
                "section": q.get_section_display(),
                "question_text": q.question_text,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "saved_answer": saved_answers.get(q.id, ""),
            })

        context = {
            "assessment": assessment,
            "questions_data": questions_data,
            "total_questions": len(questions_data),
            "remaining_seconds": remaining_seconds,
            "deadline_iso": deadline.isoformat(),
        }
        return render(request, "assessments/test_take.html", context)

    # Fallback gate
    return render(request, "assessments/test_gate.html", {"gate_type": "closed", "assessment": assessment})


@require_POST
def test_start(request, token):
    """Transition assessment status from PENDING to ONGOING when candidate clicks Start."""
    if not request.user.is_authenticated:
        return redirect(f"/candidate/login/?next=/test/{token}/")

    assessment = get_object_or_404(Assessment, token=token)

    if assessment.candidate != request.user:
        raise PermissionDenied("You are not authorized to start this assessment.")

    now = timezone.now()
    if now < assessment.start_time or now > assessment.expire_time:
        messages.error(request, "Assessment window is currently closed.")
        return redirect("assessments:test_entry", token=token)

    if assessment.status == Assessment.Status.PENDING:
        assessment.status = Assessment.Status.ONGOING
        assessment.save(update_fields=["status", "updated_at"])

    return redirect("assessments:test_entry", token=token)


@require_POST
def test_save_answer(request, token):
    """AJAX endpoint to auto-save single answer choice during test taking."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "unauthenticated"}, status=401)

    assessment = get_object_or_404(Assessment, token=token)

    if assessment.candidate != request.user:
        return JsonResponse({"error": "unauthorized"}, status=403)

    if assessment.status != Assessment.Status.ONGOING:
        return JsonResponse({"error": "test_not_active"}, status=400)

    now = timezone.now()
    if now > assessment.deadline + timedelta(seconds=15):
        return JsonResponse({"error": "deadline_passed"}, status=400)

    try:
        data = json.loads(request.body.decode("utf-8"))
        question_id = int(data.get("question_id"))
        selected_option = str(data.get("selected_option", "")).strip().upper()
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "invalid_payload"}, status=400)

    if selected_option not in ("A", "B", "C", "D"):
        return JsonResponse({"error": "invalid_option"}, status=400)

    # Verify question belongs to this assessment
    aq_exists = AssessmentQuestion.objects.filter(
        assessment=assessment, question_id=question_id
    ).exists()
    if not aq_exists:
        return JsonResponse({"error": "question_not_in_assessment"}, status=400)

    question = get_object_or_404(Question, pk=question_id)
    is_correct = (selected_option == question.correct_answer)

    Answer.objects.update_or_create(
        assessment=assessment,
        question=question,
        defaults={
            "selected_answer": selected_option,
            "is_correct": is_correct,
        },
    )

    return JsonResponse({"status": "ok", "question_id": question_id, "saved_option": selected_option})


@require_POST
def test_submit(request, token):
    """Final test submission, auto grading, and redirect to result."""
    if not request.user.is_authenticated:
        return redirect(f"/candidate/login/?next=/test/{token}/")

    assessment = get_object_or_404(Assessment, token=token)

    if assessment.candidate != request.user:
        raise PermissionDenied("You are not authorized to submit this assessment.")

    # Guard against duplicate submission
    if assessment.status == Assessment.Status.COMPLETED:
        if hasattr(assessment, "result"):
            return redirect("results:candidate_result", result_id=assessment.result.id)
        return redirect("candidates:candidate_dashboard")

    now = timezone.now()
    # Check server deadline (15-second grace period for network submission)
    if now > assessment.deadline + timedelta(seconds=15) and now > assessment.expire_time:
        assessment.status = Assessment.Status.EXPIRED
        assessment.candidate_status = Assessment.CandidateStatus.NOT_ATTENDED
        assessment.save(update_fields=["status", "candidate_status", "updated_at"])
        messages.error(request, "The submission deadline has expired. This assessment has been closed.")
        return redirect("assessments:test_entry", token=token)

    # Extract all answers from POST
    answers_dict = {}
    for key, val in request.POST.items():
        if key.startswith("q_"):
            try:
                q_id = int(key.replace("q_", ""))
                opt = str(val).strip().upper()
                if opt in ("A", "B", "C", "D"):
                    answers_dict[q_id] = opt
            except ValueError:
                continue

    # Also merge any answers previously saved via AJAX in Answer model
    existing_answers = Answer.objects.filter(assessment=assessment)
    for ans in existing_answers:
        if ans.question_id not in answers_dict:
            answers_dict[ans.question_id] = ans.selected_answer

    result = grade_and_complete_assessment(assessment, answers_dict)
    messages.success(request, "Assessment submitted successfully! Your results are available below.")
    return redirect("results:candidate_result", result_id=result.id)


def cron_expire_assessments(request):
    """Secure webhook endpoint for scheduled assessment expiry (e.g. Vercel Cron or Task Scheduler).

    Requires matching CRON_SECRET_KEY header or query token to prevent unauthorized access.
    """
    cron_secret = getattr(settings, "CRON_SECRET_KEY", "")
    auth_header = request.headers.get("Authorization", "")
    provided_token = ""

    if auth_header.startswith("Bearer "):
        provided_token = auth_header.split("Bearer ", 1)[1].strip()
    elif "key" in request.GET:
        provided_token = request.GET.get("key", "").strip()

    if not cron_secret or provided_token != cron_secret:
        return JsonResponse({"error": "unauthorized", "message": "Invalid or missing cron authorization key."}, status=403)

    count = expire_past_due_assessments()
    return JsonResponse({"status": "success", "expired_count": count})

