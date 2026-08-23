"""Views for employer assessment management and candidate test taking."""

import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import F, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST



from accounts.decorators import candidate_required, employer_required
from accounts.models import CandidateProfile
from assessments.ai_shortlist_service import analyze_assessment_with_ai, analyze_campaign_assessments
from assessments.code_executor import get_code_executor
from assessments.coding_bank import ensure_coding_bank_seeded
from assessments.email_service import send_assessment_invitation
from assessments.forms import AssessmentCreateForm
from assessments.models import (
    Answer,
    Assessment,
    AssessmentCodingQuestion,
    AssessmentGroup,
    AssessmentQuestion,
    CodingQuestion,
    CodingSubmission,
    CodingTestCase,
    Question,
)
from assessments.question_bank import ensure_question_bank_seeded
from assessments.services import expire_past_due_assessments, grade_and_complete_assessment



# ---------------------------------------------------------------------------
# Employer Assessment & Campaign Views
# ---------------------------------------------------------------------------

@employer_required
def employer_assessment_create(request):
    """Create and configure an assessment campaign for one or many registered candidates."""
    ensure_question_bank_seeded()
    ensure_coding_bank_seeded()

    initial_cand_id = request.GET.get("candidate_id")
    initial_user = None
    if initial_cand_id:
        try:
            cand_profile = CandidateProfile.objects.select_related("user").get(pk=initial_cand_id)
            initial_user = cand_profile.user
        except CandidateProfile.DoesNotExist:
            pass

    logical_bank_count = Question.objects.filter(section=Question.Sections.LOGICAL).count()
    quant_bank_count = Question.objects.filter(section=Question.Sections.QUANTITATIVE).count()
    tech_bank_count = Question.objects.filter(section=Question.Sections.TECHNICAL).count()
    coding_bank_count = CodingQuestion.objects.count()

    form = AssessmentCreateForm(
        request.POST or None,
        initial_candidate=initial_user,
    )

    candidate_profiles_qs = CandidateProfile.objects.select_related("user").all().order_by("-created_at")
    candidates_meta = {}
    for cp in candidate_profiles_qs:
        # Check if candidate has an existing active assessment created by this employer
        has_active = Assessment.objects.filter(
            employer=request.user,
            candidate=cp.user,
            status__in=[Assessment.Status.PENDING, Assessment.Status.ONGOING],
        ).exists()

        candidates_meta[str(cp.user_id)] = {
            "id": cp.user_id,
            "name": cp.user.get_full_name() or cp.user.username,
            "email": cp.user.email,
            "phone": cp.phone or "Not specified",
            "education": cp.education or "Not specified",
            "skills": cp.skills or "Not specified",
            "experience": cp.experience or 0,
            "completed": cp.profile_completed,
            "percentage": cp.completion_percentage,
            "has_active_assessment": has_active,
        }

    if request.method == "POST" and form.is_valid():
        selected_candidates = form.cleaned_data["selected_candidates"]
        title = form.cleaned_data["title"]
        start_datetime = form.cleaned_data["start_datetime"]
        expire_datetime = form.cleaned_data["expire_datetime"]
        duration_minutes = form.cleaned_data["duration_minutes"]
        sections = form.cleaned_data["sections"]
        logical_count = form.cleaned_data.get("logical_count") or 0
        quant_count = form.cleaned_data.get("quant_count") or 0
        technical_count = form.cleaned_data.get("technical_count") or 0
        include_coding = form.cleaned_data.get("include_coding", False)
        coding_count = form.cleaned_data.get("coding_count") or 0

        # Pre-select randomized questions for this assessment batch once
        selected_mcq_questions = []
        if "LOGICAL" in sections and logical_count > 0:
            selected_mcq_questions.extend(
                list(Question.objects.filter(section=Question.Sections.LOGICAL).order_by("?")[:logical_count])
            )
        if "QUANTITATIVE" in sections and quant_count > 0:
            selected_mcq_questions.extend(
                list(Question.objects.filter(section=Question.Sections.QUANTITATIVE).order_by("?")[:quant_count])
            )
        if "TECHNICAL" in sections and technical_count > 0:
            selected_mcq_questions.extend(
                list(Question.objects.filter(section=Question.Sections.TECHNICAL).order_by("?")[:technical_count])
            )

        selected_coding_questions = []
        if include_coding and coding_count > 0:
            selected_coding_questions = list(CodingQuestion.objects.order_by("?")[:coding_count])

        # 1. Create AssessmentGroup (Campaign) ONCE
        group = AssessmentGroup.objects.create(
            employer=request.user,
            title=title,
            start_time=start_datetime,
            expire_time=expire_datetime,
            duration_minutes=duration_minutes,
            has_coding=include_coding,
            total_mcq_count=len(selected_mcq_questions),
            total_coding_count=len(selected_coding_questions),
        )

        created_assessments = []
        skipped_duplicates = []
        emails_sent_count = 0

        # 2. Create individual Assessment assignments for each selected candidate
        for cand_user in selected_candidates:
            # Check duplicate assignment in this group
            if Assessment.objects.filter(group=group, candidate=cand_user).exists():
                skipped_duplicates.append(cand_user)
                continue

            assessment = Assessment.objects.create(
                group=group,
                employer=request.user,
                candidate=cand_user,
                title=title,
                start_time=start_datetime,
                expire_time=expire_datetime,
                duration_minutes=duration_minutes,
                status=Assessment.Status.PENDING,
                candidate_status=Assessment.CandidateStatus.NOT_STARTED,
                has_coding=include_coding,
            )
            created_assessments.append(assessment)

            # Bulk link MCQ questions
            if selected_mcq_questions:
                q_links = [
                    AssessmentQuestion(assessment=assessment, question=q, order=idx + 1)
                    for idx, q in enumerate(selected_mcq_questions)
                ]
                AssessmentQuestion.objects.bulk_create(q_links)

            # Bulk link Coding questions & scaffold submissions
            if selected_coding_questions:
                coding_links = [
                    AssessmentCodingQuestion(assessment=assessment, question=cq, order=c_idx + 1)
                    for c_idx, cq in enumerate(selected_coding_questions)
                ]
                AssessmentCodingQuestion.objects.bulk_create(coding_links)

                for cq in selected_coding_questions:
                    CodingSubmission.objects.get_or_create(
                        assessment=assessment,
                        question=cq,
                        defaults={
                            "language": "python",
                            "source_code": "",
                            "total_test_cases": cq.test_cases.count(),
                        },
                    )

            # Optional Firestore synchronization
            try:
                from services.firebase_service import sync_assessment_to_firestore
                q_ids = [q.id for q in selected_mcq_questions]
                sync_assessment_to_firestore(assessment, q_ids)
            except Exception:
                pass

            # Dispatch invitation email
            email_delivered = send_assessment_invitation(assessment, request=request)
            if email_delivered:
                emails_sent_count += 1

        # Flash outcome message
        cand_count = len(created_assessments)
        dup_count = len(skipped_duplicates)
        msg = f"Assessment campaign '{title}' created successfully! Assigned to {cand_count} candidate(s)."
        if emails_sent_count > 0:
            msg += f" {emails_sent_count} invitation email(s) dispatched."
        if dup_count > 0:
            msg += f" ({dup_count} duplicate candidate assignment(s) prevented)."

        messages.success(request, msg)
        return redirect("assessments:employer_campaign_detail", group_id=group.id)

    context = {
        "form": form,
        "logical_bank_count": logical_bank_count,
        "quant_bank_count": quant_bank_count,
        "tech_bank_count": tech_bank_count,
        "coding_bank_count": coding_bank_count,
        "candidate_profiles": candidate_profiles_qs,
        "candidates_meta_json": json.dumps(candidates_meta),
    }
    return render(request, "assessments/create_assessment.html", context)


@employer_required
def employer_campaign_detail(request, group_id):
    """Campaign dashboard view with candidate matrix, metrics, AI shortlisting, and filters."""
    group = get_object_or_404(AssessmentGroup, pk=group_id, employer=request.user)

    # Base query for all assessments in this campaign
    assessments_qs = (
        group.assessments.select_related("candidate", "candidate__candidate_profile", "result")
        .prefetch_related("coding_submissions")
        .order_by("-created_at")
    )

    # Calculate overall campaign statistics (Parts 4 & 10)
    total_assigned = assessments_qs.count()
    completed_count = assessments_qs.filter(status=Assessment.Status.COMPLETED).count()
    in_progress_count = assessments_qs.filter(status=Assessment.Status.ONGOING).count()
    not_started_count = assessments_qs.filter(
        status=Assessment.Status.PENDING,
        candidate_status=Assessment.CandidateStatus.NOT_STARTED,
    ).count()
    missed_count = assessments_qs.filter(
        models.Q(status=Assessment.Status.EXPIRED)
        | models.Q(candidate_status=Assessment.CandidateStatus.NOT_ATTENDED)
    ).count()
    auto_submitted_count = assessments_qs.filter(
        models.Q(auto_submitted_for_malpractice=True)
        | models.Q(submission_reason__icontains="malpractice")
        | models.Q(violation_count__gte=3)
    ).count()
    malpractice_count = assessments_qs.filter(
        models.Q(malpractice_status=True) | models.Q(violation_count__gt=0)
    ).count()

    # AI Shortlist Recommendations Summary
    ai_strong_count = assessments_qs.filter(ai_recommendation=Assessment.AIRecommendation.STRONG_MATCH).count()
    ai_review_count = assessments_qs.filter(ai_recommendation=Assessment.AIRecommendation.REVIEW_RECOMMENDED).count()
    ai_low_count = assessments_qs.filter(ai_recommendation=Assessment.AIRecommendation.LOW_MATCH).count()
    ai_pending_count = total_assigned - (ai_strong_count + ai_review_count + ai_low_count)

    # Employer Shortlisted Count
    shortlisted_count = assessments_qs.filter(is_shortlisted=True).count()

    # Filter by status / category
    filter_status = request.GET.get("status", "all").strip().lower()
    filtered_qs = assessments_qs

    if filter_status == "completed":
        filtered_qs = filtered_qs.filter(status=Assessment.Status.COMPLETED)
    elif filter_status == "in_progress":
        filtered_qs = filtered_qs.filter(status=Assessment.Status.ONGOING)
    elif filter_status == "not_started":
        filtered_qs = filtered_qs.filter(
            status=Assessment.Status.PENDING,
            candidate_status=Assessment.CandidateStatus.NOT_STARTED,
        )
    elif filter_status == "missed":
        filtered_qs = filtered_qs.filter(
            models.Q(status=Assessment.Status.EXPIRED)
            | models.Q(candidate_status=Assessment.CandidateStatus.NOT_ATTENDED)
        )
    elif filter_status == "auto_submitted":
        filtered_qs = filtered_qs.filter(
            models.Q(auto_submitted_for_malpractice=True)
            | models.Q(submission_reason__icontains="malpractice")
            | models.Q(violation_count__gte=3)
        )
    elif filter_status == "malpractice":
        filtered_qs = filtered_qs.filter(
            models.Q(malpractice_status=True) | models.Q(violation_count__gt=0)
        )
    elif filter_status == "shortlisted":
        filtered_qs = filtered_qs.filter(is_shortlisted=True)
    elif filter_status == "ai_strong":
        filtered_qs = filtered_qs.filter(ai_recommendation=Assessment.AIRecommendation.STRONG_MATCH)
    elif filter_status == "ai_review":
        filtered_qs = filtered_qs.filter(ai_recommendation=Assessment.AIRecommendation.REVIEW_RECOMMENDED)
    elif filter_status == "ai_low":
        filtered_qs = filtered_qs.filter(ai_recommendation=Assessment.AIRecommendation.LOW_MATCH)

    # Search filter by candidate name / email / skills
    search_query = request.GET.get("q", "").strip()
    if search_query:
        filtered_qs = filtered_qs.filter(
            models.Q(candidate__first_name__icontains=search_query)
            | models.Q(candidate__last_name__icontains=search_query)
            | models.Q(candidate__email__icontains=search_query)
            | models.Q(candidate__username__icontains=search_query)
            | models.Q(candidate__candidate_profile__skills__icontains=search_query)
        )

    context = {
        "group": group,
        "assessments": filtered_qs,
        "filter_status": filter_status,
        "search_query": search_query,
        "total_assigned": total_assigned,
        "completed_count": completed_count,
        "in_progress_count": in_progress_count,
        "not_started_count": not_started_count,
        "missed_count": missed_count,
        "auto_submitted_count": auto_submitted_count,
        "malpractice_count": malpractice_count,
        "ai_strong_count": ai_strong_count,
        "ai_review_count": ai_review_count,
        "ai_low_count": ai_low_count,
        "ai_pending_count": ai_pending_count,
        "shortlisted_count": shortlisted_count,
    }
    return render(request, "assessments/campaign_detail.html", context)


@employer_required
@require_POST
def employer_campaign_ai_shortlist(request, group_id):
    """Run AI shortlisting analysis for all completed candidates in an assessment campaign."""
    group = get_object_or_404(AssessmentGroup, pk=group_id, employer=request.user)
    assessments_qs = group.assessments.all()

    analysis_data = analyze_campaign_assessments(assessments_qs)

    if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.POST.get("format") == "json":
        return JsonResponse({
            "status": "ok",
            "message": f"AI shortlisting completed for {len(analysis_data['results'])} candidates.",
            "data": analysis_data,
        })

    messages.success(
        request,
        f"AI shortlisting analysis completed for '{group.title}'. Review recommendations below.",
    )
    return redirect("assessments:employer_campaign_detail", group_id=group.id)


@employer_required
@require_POST
def employer_campaign_shortlist_action(request, group_id):
    """Execute employer shortlist actions: shortlist, remove, or toggle."""
    group = get_object_or_404(AssessmentGroup, pk=group_id, employer=request.user)

    action = request.POST.get("action", "").strip().lower()
    raw_ids = request.POST.getlist("assessment_ids")
    notes = request.POST.get("notes", "").strip()

    if not raw_ids and request.POST.get("assessment_id"):
        raw_ids = [request.POST.get("assessment_id")]

    # If body is JSON
    if not raw_ids and request.body:
        try:
            body_data = json.loads(request.body.decode("utf-8"))
            action = body_data.get("action", action)
            raw_ids = body_data.get("assessment_ids", [])
            notes = body_data.get("notes", notes)
            if not raw_ids and body_data.get("assessment_id"):
                raw_ids = [body_data.get("assessment_id")]
        except Exception:
            pass

    target_assessments = Assessment.objects.filter(
        group=group,
        employer=request.user,
        id__in=raw_ids,
    )

    updated_count = 0
    now = timezone.now()

    if action == "shortlist":
        updated_count = target_assessments.update(
            is_shortlisted=True,
            shortlisted_at=now,
            shortlist_notes=notes or models.F("shortlist_notes"),
        )
        msg = f"Shortlisted {updated_count} candidate(s) successfully."
    elif action == "remove":
        updated_count = target_assessments.update(
            is_shortlisted=False,
            shortlisted_at=None,
        )
        msg = f"Removed {updated_count} candidate(s) from shortlist."
    elif action == "toggle":
        for a in target_assessments:
            a.is_shortlisted = not a.is_shortlisted
            a.shortlisted_at = now if a.is_shortlisted else None
            a.save(update_fields=["is_shortlisted", "shortlisted_at"])
            updated_count += 1
        msg = "Shortlist status updated."
    else:
        msg = "No action specified."

    if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.POST.get("format") == "json":
        return JsonResponse({
            "status": "ok",
            "message": msg,
            "updated_count": updated_count,
            "shortlisted_count": group.shortlisted_count,
        })

    messages.success(request, msg)
    return redirect("assessments:employer_campaign_detail", group_id=group.id)


@employer_required
def employer_campaign_list(request):
    """List all assessment campaigns created by this employer."""
    campaigns = (
        AssessmentGroup.objects.filter(employer=request.user)
        .prefetch_related("assessments")
        .order_by("-created_at")
    )
    context = {
        "campaigns": campaigns,
        "total_campaigns": campaigns.count(),
    }
    return render(request, "assessments/campaign_list.html", context)


@employer_required
def employer_assessment_list(request):
    """List all individual candidate assessments created by this employer."""
    assessments = (
        Assessment.objects.filter(employer=request.user)
        .select_related("candidate", "result", "group")
        .order_by("-created_at")
    )
    context = {
        "assessments": assessments,
        "total_count": assessments.count(),
    }
    return render(request, "assessments/employer_assessment_list.html", context)


@employer_required
def employer_ai_question_generator(request):
    """Employer interface for generating original Aptitude and Coding questions via AI."""
    from assessments.ai_generator import (
        generate_aptitude_questions,
        generate_coding_questions,
        save_aptitude_questions,
        save_coding_questions,
    )

    generated_questions = []
    generated_coding = []
    mode = "aptitude"
    section = Question.Sections.LOGICAL
    difficulty = Question.Difficulties.MEDIUM
    count = 5
    coding_category = CodingQuestion.Categories.ARRAYS
    language = "python"
    step = "config"

    if request.method == "POST":
        action = request.POST.get("action", "generate")

        if action == "generate":
            mode = request.POST.get("mode", "aptitude")
            difficulty = request.POST.get("difficulty", Question.Difficulties.MEDIUM)
            try:
                count = int(request.POST.get("count", 5))
                count = max(1, min(20, count))
            except ValueError:
                count = 5

            if mode == "aptitude":
                section = request.POST.get("section", Question.Sections.LOGICAL)
                generated_questions = generate_aptitude_questions(
                    section=section,
                    difficulty=difficulty,
                    count=count,
                )
                step = "preview"
                messages.info(request, f"Generated {len(generated_questions)} new {section} questions. Review them below before saving to Question Bank.")
            else:  # coding
                coding_category = request.POST.get("coding_category", CodingQuestion.Categories.ARRAYS)
                language = request.POST.get("language", "python")
                generated_coding = generate_coding_questions(
                    category=coding_category,
                    difficulty=difficulty,
                    language=language,
                    count=count,
                )
                step = "preview"
                messages.info(request, f"Generated {len(generated_coding)} new coding challenges in category '{coding_category}'. Review them below before saving.")

        elif action == "save_aptitude":
            raw_payload = request.POST.get("questions_payload", "[]")
            try:
                payload = json.loads(raw_payload)
                saved = save_aptitude_questions(payload)
                messages.success(request, f"Successfully added {len(saved)} AI-generated questions to the Question Bank!")
                return redirect("assessments:employer_assessment_create")
            except Exception as exc:
                messages.error(request, f"Error saving generated questions: {exc}")

        elif action == "save_coding":
            raw_payload = request.POST.get("coding_payload", "[]")
            try:
                payload = json.loads(raw_payload)
                saved = save_coding_questions(payload)
                messages.success(request, f"Successfully added {len(saved)} AI-generated coding challenges to the Question Bank!")
                return redirect("assessments:employer_assessment_create")
            except Exception as exc:
                messages.error(request, f"Error saving generated coding problems: {exc}")

    context = {
        "step": step,
        "mode": mode,
        "section": section,
        "difficulty": difficulty,
        "count": count,
        "coding_category": coding_category,
        "language": language,
        "sections": Question.Sections.choices,
        "difficulties": Question.Difficulties.choices,
        "coding_categories": CodingQuestion.Categories.choices,
        "generated_questions": generated_questions,
        "generated_coding": generated_coding,
        "generated_questions_json": json.dumps(generated_questions),
        "generated_coding_json": json.dumps(generated_coding),
        "total_aptitude_bank": Question.objects.count(),
        "total_coding_bank": CodingQuestion.objects.count(),
    }
    return render(request, "assessments/ai_question_generator.html", context)



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
        coding_qs_count = assessment.coding_questions.count() if assessment.has_coding else 0
        return render(
            request,
            "assessments/test_instructions.html",
            {
                "assessment": assessment,
                "sections_display": ", ".join(sorted(sections_found)),
                "question_count": questions_qs.count(),
                "has_coding": assessment.has_coding,
                "coding_questions_count": coding_qs_count,
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
            "has_coding": assessment.has_coding,
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
        assessment.start_time = now
        assessment.save(update_fields=["status", "start_time", "updated_at"])
        try:
            from services.firebase_service import update_assessment_status_in_firestore
            update_assessment_status_in_firestore(assessment.id, Assessment.Status.ONGOING)
        except Exception:
            pass

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

    try:
        from services.firebase_service import sync_answer_to_firestore
        sync_answer_to_firestore(assessment.id, question_id, selected_option, is_correct)
    except Exception:
        pass

    return JsonResponse({"status": "ok", "question_id": question_id, "saved_option": selected_option})


def test_coding(request, token):
    """Render the professional coding assessment interface."""
    if not request.user.is_authenticated:
        return redirect(f"/candidate/login/?next=/test/{token}/coding/")

    assessment = get_object_or_404(Assessment, token=token)

    if assessment.candidate != request.user:
        raise PermissionDenied("You are not authorized to view this assessment.")

    # Status check
    if assessment.status == Assessment.Status.COMPLETED:
        if hasattr(assessment, "result"):
            return redirect("results:candidate_result", result_id=assessment.result.id)
        return redirect("candidates:candidate_dashboard")

    if assessment.status != Assessment.Status.ONGOING:
        return redirect("assessments:test_entry", token=token)

    now = timezone.now()
    deadline = assessment.deadline
    remaining_seconds = max(0, int((deadline - now).total_seconds()))

    if remaining_seconds <= 0:
        # Auto complete
        existing_answers = {
            ans.question_id: ans.selected_answer
            for ans in Answer.objects.filter(assessment=assessment)
        }
        result = grade_and_complete_assessment(assessment, existing_answers)
        messages.info(request, "Assessment time expired. Your test has been submitted.")
        return redirect("results:candidate_result", result_id=result.id)

    assigned_coding = assessment.coding_questions.select_related("question").order_by("order", "id")
    if not assigned_coding.exists():
        return redirect("assessments:test_entry", token=token)

    problems_data = []
    for index, acq in enumerate(assigned_coding, start=1):
        cq = acq.question
        submission, _ = CodingSubmission.objects.get_or_create(
            assessment=assessment,
            question=cq,
            defaults={
                "language": "python",
                "source_code": "",
                "total_test_cases": cq.test_cases.count(),
            },
        )
        sample_tcs = [
            {
                "order": tc.order,
                "input_data": tc.input_data,
                "expected_output": tc.expected_output,
            }
            for tc in cq.test_cases.filter(is_sample=True).order_by("order")
        ]
        total_tc_count = cq.test_cases.count()
        starter = cq.starter_code.get(submission.language, "") if cq.starter_code else ""
        initial_code = submission.source_code if submission.source_code else starter

        problems_data.append({
            "index": index,
            "id": cq.id,
            "title": cq.title,
            "category": cq.get_category_display() if hasattr(cq, "get_category_display") else cq.category,
            "difficulty": cq.get_difficulty_display(),
            "description": cq.description,
            "input_format": cq.input_format,
            "output_format": cq.output_format,
            "constraints": cq.constraints,
            "sample_input": cq.sample_input,
            "sample_output": cq.sample_output,
            "explanation": cq.explanation,
            "starter_code": cq.starter_code,
            "current_language": submission.language,
            "saved_code": initial_code,
            "is_submitted": submission.is_submitted,
            "sample_test_cases": sample_tcs,
            "passed_test_cases": submission.passed_test_cases,
            "total_test_cases": total_tc_count,
            "score": float(submission.score),
            "last_saved_at": submission.last_saved_at.strftime("%I:%M:%S %p") if submission.last_saved_at else "",
        })


    context = {
        "assessment": assessment,
        "problems_data": problems_data,
        "problems_data_json": json.dumps(problems_data),
        "total_coding_questions": len(problems_data),
        "remaining_seconds": remaining_seconds,
        "deadline_iso": deadline.isoformat(),
    }
    return render(request, "assessments/test_coding.html", context)


@require_POST
def test_save_code(request, token):
    """AJAX endpoint to auto-save candidate's coding solution (debounced)."""
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
        language = str(data.get("language", "python")).strip().lower()
        source_code = str(data.get("source_code", ""))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "invalid_payload"}, status=400)

    cq = get_object_or_404(CodingQuestion, pk=question_id)

    # Verify coding question belongs to assessment
    acq_exists = AssessmentCodingQuestion.objects.filter(assessment=assessment, question=cq).exists()
    if not acq_exists:
        return JsonResponse({"error": "question_not_in_assessment"}, status=400)

    submission, _ = CodingSubmission.objects.update_or_create(
        assessment=assessment,
        question=cq,
        defaults={
            "language": language,
            "source_code": source_code,
            "total_test_cases": cq.test_cases.count(),
        },
    )

    last_saved_time = timezone.localtime(timezone.now()).strftime("%I:%M:%S %p")
    return JsonResponse({
        "status": "ok",
        "question_id": question_id,
        "last_saved": last_saved_time,
        "language": language,
    })


@require_POST
def test_run_code(request, token):
    """AJAX endpoint to run candidate code against visible sample test cases."""
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
        language = str(data.get("language", "python")).strip().lower()
        source_code = str(data.get("source_code", ""))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "invalid_payload"}, status=400)

    cq = get_object_or_404(CodingQuestion, pk=question_id)
    sample_tcs = cq.test_cases.filter(is_sample=True).order_by("order")

    executor = get_code_executor()
    summary = executor.execute_test_cases(language, source_code, list(sample_tcs), only_samples=True)

    # Also save code
    CodingSubmission.objects.update_or_create(
        assessment=assessment,
        question=cq,
        defaults={
            "language": language,
            "source_code": source_code,
            "total_test_cases": cq.test_cases.count(),
        },
    )

    last_saved_time = timezone.localtime(timezone.now()).strftime("%I:%M:%S %p")
    response_data = summary.to_dict(hide_hidden_details=False)
    response_data["last_saved"] = last_saved_time
    return JsonResponse(response_data)


@require_POST
def test_submit_code_problem(request, token):
    """AJAX endpoint to submit solution for a coding problem (evaluates all test cases)."""
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
        language = str(data.get("language", "python")).strip().lower()
        source_code = str(data.get("source_code", ""))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "invalid_payload"}, status=400)

    cq = get_object_or_404(CodingQuestion, pk=question_id)
    all_tcs = cq.test_cases.all().order_by("order")

    executor = get_code_executor()
    summary = executor.execute_test_cases(language, source_code, list(all_tcs), only_samples=False)

    all_passed = (summary.passed_test_cases == summary.total_test_cases and summary.total_test_cases > 0)

    # Save candidate submission & scores
    submission, _ = CodingSubmission.objects.update_or_create(
        assessment=assessment,
        question=cq,
        defaults={
            "language": language,
            "source_code": source_code,
            "passed_test_cases": summary.passed_test_cases,
            "total_test_cases": summary.total_test_cases,
            "score": Decimal(str(summary.score_percentage)),
            "is_submitted": all_passed,
        },
    )

    last_saved_time = timezone.localtime(timezone.now()).strftime("%I:%M:%S %p")
    # Hide hidden test case details to prevent leaks
    response_data = summary.to_dict(hide_hidden_details=True)
    response_data["last_saved"] = last_saved_time
    response_data["problem_score"] = float(submission.score)
    response_data["all_passed"] = all_passed
    response_data["is_submitted"] = all_passed
    response_data["message"] = (
        "All test cases passed! Question completed."
        if all_passed
        else "Submission failed — please fix your code and try again."
    )
    return JsonResponse(response_data)



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

    # If candidate clicked "Proceed to Coding" from the Aptitude section:
    action = request.POST.get("action", "")
    if assessment.has_coding and action == "proceed_coding":
        for q_id, opt in answers_dict.items():
            try:
                q_obj = Question.objects.get(pk=q_id)
                Answer.objects.update_or_create(
                    assessment=assessment,
                    question=q_obj,
                    defaults={
                        "selected_answer": opt,
                        "is_correct": (opt == q_obj.correct_answer),
                    },
                )
            except Question.DoesNotExist:
                continue
        return redirect("assessments:test_coding", token=token)

    result = grade_and_complete_assessment(assessment, answers_dict)
    messages.success(request, "Assessment submitted successfully! Your results are available below.")
    return redirect("results:candidate_result", result_id=result.id)


@require_POST
def test_record_violation(request, token):
    """Record a proctoring violation event and automatically terminate if limit is reached."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "unauthenticated"}, status=401)

    assessment = get_object_or_404(Assessment, token=token)
    if assessment.candidate != request.user:
        return JsonResponse({"error": "unauthorized"}, status=403)

    if assessment.status != Assessment.Status.ONGOING:
        return JsonResponse({
            "error": "test_not_active",
            "status": "terminated",
            "violation_count": assessment.violation_count,
            "auto_submitted": assessment.auto_submitted_for_malpractice,
        }, status=400)

    now = timezone.now()
    if now > assessment.deadline + timedelta(seconds=15):
        return JsonResponse({"error": "deadline_passed"}, status=400)

    try:
        data = json.loads(request.body.decode("utf-8")) if request.body else {}
        violation_type = str(data.get("violation_type", "FULLSCREEN_EXIT")).strip().upper()
    except (ValueError, TypeError, json.JSONDecodeError):
        violation_type = "FULLSCREEN_EXIT"

    # Debounce rapid duplicate events (within 2.5 seconds)
    if assessment.last_violation_at and (now - assessment.last_violation_at).total_seconds() < 2.5:
        return JsonResponse({
            "status": "warning" if assessment.violation_count < assessment.max_violations else "terminated",
            "violation_count": assessment.violation_count,
            "max_violations": assessment.max_violations,
            "remaining_warnings": max(0, assessment.max_violations - assessment.violation_count),
            "auto_submitted": assessment.auto_submitted_for_malpractice,
            "message": f"Warning {assessment.violation_count} of {assessment.max_violations}: Please remain in fullscreen.",
        })

    # Increment server-authoritative violation count
    assessment.violation_count += 1
    assessment.last_violation_type = violation_type
    assessment.last_violation_at = now

    if assessment.violation_count >= assessment.max_violations:
        assessment.malpractice_status = True
        assessment.auto_submitted_for_malpractice = True
        assessment.submission_reason = f"Assessment automatically submitted after {assessment.violation_count} proctoring violations ({violation_type.replace('_', ' ').lower()})."
        assessment.save(update_fields=[
            "violation_count", "last_violation_type", "last_violation_at",
            "malpractice_status", "auto_submitted_for_malpractice", "submission_reason", "updated_at"
        ])

        # Auto-submit and grade assessment
        existing_answers = {
            ans.question_id: ans.selected_answer
            for ans in Answer.objects.filter(assessment=assessment)
        }
        result = grade_and_complete_assessment(assessment, existing_answers)


        return JsonResponse({
            "status": "terminated",
            "violation_count": assessment.violation_count,
            "max_violations": assessment.max_violations,
            "remaining_warnings": 0,
            "auto_submitted": True,
            "message": "Assessment automatically submitted due to multiple proctoring violations.",
            "redirect_url": reverse("results:candidate_result", kwargs={"result_id": result.id}),
        })

    assessment.save(update_fields=["violation_count", "last_violation_type", "last_violation_at", "updated_at"])

    return JsonResponse({
        "status": "warning",
        "violation_count": assessment.violation_count,
        "max_violations": assessment.max_violations,
        "remaining_warnings": max(0, assessment.max_violations - assessment.violation_count),
        "auto_submitted": False,
        "message": f"⚠️ Fullscreen exited. Warning {assessment.violation_count} of {assessment.max_violations}. Please return to fullscreen to continue the assessment.",
    })




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