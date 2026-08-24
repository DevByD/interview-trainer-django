"""Admin Portal views providing platform-wide Question Bank CRUD, Assessments, Campaigns, Analytics, and Proctoring audit."""

import csv
import json
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required
from accounts.models import CandidateProfile, EmployerProfile, User
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
from dashboard.admin_forms import CodingQuestionForm, MCQQuestionForm
from dashboard.models import AdminActivityLog, log_admin_activity
from results.models import Result


# =============================================================================
# 1. ADMIN DASHBOARD OVERVIEW
# =============================================================================

@admin_required
def admin_dashboard(request):
    """Admin portal root overview with platform-wide KPIs and recent activity."""
    total_candidates = CandidateProfile.objects.count()
    total_employers = EmployerProfile.objects.count()
    total_mcq_questions = Question.objects.count()
    total_coding_questions = CodingQuestion.objects.count()
    total_questions = total_mcq_questions + total_coding_questions

    total_campaigns = AssessmentGroup.objects.count()
    total_assessments = Assessment.objects.count()
    completed_assessments = Assessment.objects.filter(status=Assessment.Status.COMPLETED).count()
    active_assessments = Assessment.objects.filter(
        status__in=[Assessment.Status.PENDING, Assessment.Status.ONGOING]
    ).count()

    results_qs = Result.objects.all()
    avg_overall_score = results_qs.aggregate(avg=Avg("overall_score"))["avg"] or 0
    total_violations = Assessment.objects.aggregate(total=Count("id", filter=Q(violation_count__gt=0)))["total"] or 0
    auto_submitted_malpractice = Assessment.objects.filter(auto_submitted_for_malpractice=True).count()

    recent_campaigns = (
        AssessmentGroup.objects.select_related("employer", "employer__employer_profile")
        .prefetch_related("assessments")
        .order_by("-created_at")[:5]
    )

    recent_results = (
        Result.objects.select_related("assessment", "assessment__candidate", "assessment__employer")
        .order_by("-completed_at")[:6]
    )

    context = {
        "total_candidates": total_candidates,
        "total_employers": total_employers,
        "total_questions": total_questions,
        "total_mcq_questions": total_mcq_questions,
        "total_coding_questions": total_coding_questions,
        "total_campaigns": total_campaigns,
        "total_assessments": total_assessments,
        "completed_assessments": completed_assessments,
        "active_assessments": active_assessments,
        "avg_overall_score": round(float(avg_overall_score), 1),
        "total_violations": total_violations,
        "auto_submitted_malpractice": auto_submitted_malpractice,
        "recent_campaigns": recent_campaigns,
        "recent_results": recent_results,
    }
    return render(request, "admin_portal/dashboard.html", context)


# =============================================================================
# 2. QUESTION BANK — FULL CRUD, PROVENANCE & FILTERS
# =============================================================================

@admin_required
def admin_questions_list(request):
    """Unified question bank management with search, subject/category filters, provenance, active filters, and pagination."""
    q_type = request.GET.get("type", "all").strip().lower()
    search_query = request.GET.get("q", "").strip()
    section_filter = request.GET.get("section", "").strip()
    difficulty_filter = request.GET.get("difficulty", "").strip()
    source_filter = request.GET.get("source", "").strip()
    status_filter = request.GET.get("status", "").strip().lower()

    # Querysets
    mcq_qs = Question.objects.all().order_by("-created_at", "-id")
    coding_qs = CodingQuestion.objects.all().order_by("-created_at", "-id")

    # Apply Filters to MCQ
    if search_query:
        mcq_qs = mcq_qs.filter(
            Q(question_text__icontains=search_query)
            | Q(category__icontains=search_query)
            | Q(explanation__icontains=search_query)
            | Q(option_a__icontains=search_query)
            | Q(option_b__icontains=search_query)
            | Q(option_c__icontains=search_query)
            | Q(option_d__icontains=search_query)
        )
    if section_filter and section_filter in Question.Sections.values:
        mcq_qs = mcq_qs.filter(section=section_filter)
    if difficulty_filter and difficulty_filter in Question.Difficulties.values:
        mcq_qs = mcq_qs.filter(difficulty=difficulty_filter)
    if source_filter and source_filter in Question.SourceTypes.values:
        mcq_qs = mcq_qs.filter(source_type=source_filter)
    if status_filter == "active":
        mcq_qs = mcq_qs.filter(is_active=True)
    elif status_filter == "inactive":
        mcq_qs = mcq_qs.filter(is_active=False)

    # Apply Filters to Coding
    if search_query:
        coding_qs = coding_qs.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__icontains=search_query)
            | Q(explanation__icontains=search_query)
        )
    if section_filter:
        if section_filter in CodingQuestion.Categories.values:
            coding_qs = coding_qs.filter(category=section_filter)
        elif section_filter in Question.Sections.values:
            coding_qs = coding_qs.none()
    if difficulty_filter and difficulty_filter in Question.Difficulties.values:
        coding_qs = coding_qs.filter(difficulty=difficulty_filter)
    if source_filter and source_filter in Question.SourceTypes.values:
        coding_qs = coding_qs.filter(source_type=source_filter)
    if status_filter == "active":
        coding_qs = coding_qs.filter(is_active=True)
    elif status_filter == "inactive":
        coding_qs = coding_qs.filter(is_active=False)

    # Unified List or Segregated by type
    items = []
    if q_type == "mcq":
        for q in mcq_qs:
            items.append({
                "id": q.id,
                "type": "mcq",
                "type_display": "MCQ Aptitude",
                "title": q.question_text,
                "subject": q.get_section_display(),
                "category": q.category or q.get_section_display(),
                "difficulty": q.get_difficulty_display(),
                "difficulty_val": q.difficulty,
                "source_type": q.source_type,
                "source_type_display": q.get_source_type_display(),
                "ai_provider": q.ai_provider,
                "is_active": q.is_active,
                "is_reviewed": q.is_reviewed,
                "is_approved": q.is_approved,
                "usage_count": q.usage_count,
                "created_at": q.created_at,
                "obj": q,
            })
    elif q_type == "coding":
        for cq in coding_qs:
            items.append({
                "id": cq.id,
                "type": "coding",
                "type_display": "Coding Challenge",
                "title": cq.title,
                "subject": "Coding",
                "category": cq.get_category_display(),
                "difficulty": cq.get_difficulty_display(),
                "difficulty_val": cq.difficulty,
                "source_type": cq.source_type,
                "source_type_display": cq.get_source_type_display(),
                "ai_provider": cq.ai_provider,
                "is_active": cq.is_active,
                "is_reviewed": cq.is_reviewed,
                "is_approved": cq.is_approved,
                "usage_count": cq.usage_count,
                "created_at": cq.created_at,
                "obj": cq,
            })
    else:
        # All items
        for q in mcq_qs:
            items.append({
                "id": q.id,
                "type": "mcq",
                "type_display": "MCQ Aptitude",
                "title": q.question_text,
                "subject": q.get_section_display(),
                "category": q.category or q.get_section_display(),
                "difficulty": q.get_difficulty_display(),
                "difficulty_val": q.difficulty,
                "source_type": q.source_type,
                "source_type_display": q.get_source_type_display(),
                "ai_provider": q.ai_provider,
                "is_active": q.is_active,
                "is_reviewed": q.is_reviewed,
                "is_approved": q.is_approved,
                "usage_count": q.usage_count,
                "created_at": q.created_at,
                "obj": q,
            })
        for cq in coding_qs:
            items.append({
                "id": cq.id,
                "type": "coding",
                "type_display": "Coding Challenge",
                "title": cq.title,
                "subject": "Coding",
                "category": cq.get_category_display(),
                "difficulty": cq.get_difficulty_display(),
                "difficulty_val": cq.difficulty,
                "source_type": cq.source_type,
                "source_type_display": cq.get_source_type_display(),
                "ai_provider": cq.ai_provider,
                "is_active": cq.is_active,
                "is_reviewed": cq.is_reviewed,
                "is_approved": cq.is_approved,
                "usage_count": cq.usage_count,
                "created_at": cq.created_at,
                "obj": cq,
            })
        items.sort(key=lambda x: x["created_at"] or timezone.now(), reverse=True)

    # Global Stats
    total_mcq = Question.objects.count()
    total_coding = CodingQuestion.objects.count()
    active_mcq = Question.objects.filter(is_active=True).count()
    active_coding = CodingQuestion.objects.filter(is_active=True).count()
    ai_mcq = Question.objects.filter(source_type=Question.SourceTypes.AI_GENERATED).count()
    ai_coding = CodingQuestion.objects.filter(source_type=Question.SourceTypes.AI_GENERATED).count()
    curated_mcq = Question.objects.filter(source_type=Question.SourceTypes.CURATED).count()

    paginator = Paginator(items, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "total_items": len(items),
        "q_type": q_type,
        "search_query": search_query,
        "section_filter": section_filter,
        "difficulty_filter": difficulty_filter,
        "source_filter": source_filter,
        "status_filter": status_filter,
        "section_choices": Question.Sections.choices,
        "coding_categories": CodingQuestion.Categories.choices,
        "difficulty_choices": Question.Difficulties.choices,
        "source_choices": Question.SourceTypes.choices,
        "stat_total_questions": total_mcq + total_coding,
        "stat_total_mcq": total_mcq,
        "stat_total_coding": total_coding,
        "stat_active_total": active_mcq + active_coding,
        "stat_inactive_total": (total_mcq + total_coding) - (active_mcq + active_coding),
        "stat_ai_total": ai_mcq + ai_coding,
        "stat_curated_total": curated_mcq,
    }
    return render(request, "admin_portal/question_bank.html", context)


@admin_required
def admin_mcq_create(request):
    """Create a new MCQ question with category, difficulty, explanation, and provenance."""
    if request.method == "POST":
        form = MCQQuestionForm(request.POST)
        if form.is_valid():
            question = form.save()
            log_admin_activity(request.user, AdminActivityLog.ActionTypes.QUESTION_CREATED, f"Created MCQ Question #{question.id} ({question.get_section_display()})", request=request)
            messages.success(request, f"MCQ Question #{question.id} created successfully!")
            return redirect("dashboard:admin_questions")
    else:
        form = MCQQuestionForm()

    return render(request, "admin_portal/mcq_form.html", {"form": form, "action": "Create"})


@admin_required
def admin_mcq_edit(request, question_id):
    """Update an existing MCQ question."""
    question = get_object_or_404(Question, pk=question_id)
    if request.method == "POST":
        form = MCQQuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            log_admin_activity(request.user, AdminActivityLog.ActionTypes.QUESTION_UPDATED, f"Updated MCQ Question #{question.id}", request=request)
            messages.success(request, f"MCQ Question #{question.id} updated successfully!")
            return redirect("dashboard:admin_questions")
    else:
        form = MCQQuestionForm(instance=question)

    return render(
        request,
        "admin_portal/mcq_form.html",
        {"form": form, "question": question, "action": "Edit"},
    )


@admin_required
def admin_coding_create(request):
    """Create a new algorithmic coding challenge with test cases and scaffolding."""
    if request.method == "POST":
        form = CodingQuestionForm(request.POST)
        if form.is_valid():
            cq = form.save()
            # Parse test cases
            tc_inputs = request.POST.getlist("tc_input[]")
            tc_outputs = request.POST.getlist("tc_output[]")
            tc_samples = request.POST.getlist("tc_is_sample[]")

            tc_objs = []
            for i in range(len(tc_inputs)):
                inp = tc_inputs[i].strip()
                outp = tc_outputs[i].strip() if i < len(tc_outputs) else ""
                if inp or outp:
                    is_sample = str(i) in tc_samples or (i < len(tc_samples) and tc_samples[i] == "1")
                    tc_objs.append(
                        CodingTestCase(
                            question=cq,
                            input_data=inp,
                            expected_output=outp,
                            is_sample=is_sample,
                            order=i + 1,
                        )
                    )
            if tc_objs:
                CodingTestCase.objects.bulk_create(tc_objs)
            else:
                # Add default sample test case if none supplied
                CodingTestCase.objects.create(
                    question=cq,
                    input_data=cq.sample_input,
                    expected_output=cq.sample_output,
                    is_sample=True,
                    order=1,
                )

            messages.success(request, f"Coding Challenge '{cq.title}' created successfully!")
            log_admin_activity(request.user, AdminActivityLog.ActionTypes.QUESTION_CREATED, f"Created Coding Challenge '{cq.title}' (#{cq.id})", request=request)
            return redirect("dashboard:admin_questions")
    else:
        form = CodingQuestionForm()

    return render(request, "admin_portal/coding_form.html", {"form": form, "action": "Create", "test_cases": []})


@admin_required
def admin_coding_edit(request, question_id):
    """Update an existing coding challenge and its test cases."""
    cq = get_object_or_404(CodingQuestion, pk=question_id)
    if request.method == "POST":
        form = CodingQuestionForm(request.POST, instance=cq)
        if form.is_valid():
            cq = form.save()
            # Replace test cases
            tc_inputs = request.POST.getlist("tc_input[]")
            tc_outputs = request.POST.getlist("tc_output[]")
            tc_samples = request.POST.getlist("tc_is_sample[]")

            cq.test_cases.all().delete()
            tc_objs = []
            for i in range(len(tc_inputs)):
                inp = tc_inputs[i].strip()
                outp = tc_outputs[i].strip() if i < len(tc_outputs) else ""
                if inp or outp:
                    is_sample = str(i) in tc_samples or (i < len(tc_samples) and tc_samples[i] == "1")
                    tc_objs.append(
                        CodingTestCase(
                            question=cq,
                            input_data=inp,
                            expected_output=outp,
                            is_sample=is_sample,
                            order=i + 1,
                        )
                    )
            if tc_objs:
                CodingTestCase.objects.bulk_create(tc_objs)

            messages.success(request, f"Coding Challenge '{cq.title}' updated successfully!")
            log_admin_activity(request.user, AdminActivityLog.ActionTypes.QUESTION_UPDATED, f"Updated Coding Challenge '{cq.title}' (#{cq.id})", request=request)
            return redirect("dashboard:admin_questions")
    else:
        form = CodingQuestionForm(instance=cq)

    test_cases = cq.test_cases.order_by("order", "id")
    return render(
        request,
        "admin_portal/coding_form.html",
        {"form": form, "question": cq, "action": "Edit", "test_cases": test_cases},
    )


@admin_required
@require_POST
def admin_question_toggle_active(request, q_type, question_id):
    """Toggle active/inactive status safely for an MCQ or Coding question."""
    if q_type == "mcq":
        q = get_object_or_404(Question, pk=question_id)
        q.is_active = not q.is_active
        q.save(update_fields=["is_active"])
        status_label = "activated" if q.is_active else "deactivated"
        log_admin_activity(request.user, AdminActivityLog.ActionTypes.QUESTION_STATUS_TOGGLED, f"{status_label.capitalize()} MCQ #{q.id}", request=request)
        messages.success(request, f"MCQ Question #{q.id} has been {status_label}.")
    elif q_type == "coding":
        cq = get_object_or_404(CodingQuestion, pk=question_id)
        cq.is_active = not cq.is_active
        cq.save(update_fields=["is_active"])
        status_label = "activated" if cq.is_active else "deactivated"
        log_admin_activity(request.user, AdminActivityLog.ActionTypes.QUESTION_STATUS_TOGGLED, f"{status_label.capitalize()} Coding Challenge '{cq.title}' (#{cq.id})", request=request)
        messages.success(request, f"Coding Challenge '{cq.title}' has been {status_label}.")
    else:
        messages.error(request, "Invalid question type specified.")

    return redirect(request.META.get("HTTP_REFERER") or "dashboard:admin_questions")


@admin_required
@require_POST
def admin_question_delete(request, q_type, question_id):
    """Safely delete or deactivate a question depending on whether it is linked to assessments."""
    if q_type == "mcq":
        q = get_object_or_404(Question, pk=question_id)
        usage = q.usage_count
        if usage > 0:
            q.is_active = False
            q.save(update_fields=["is_active"])
            log_admin_activity(request.user, AdminActivityLog.ActionTypes.QUESTION_DELETED, f"Soft-deactivated in-use MCQ #{q.id} ({usage} assessments)", request=request)
            messages.warning(
                request,
                f"Question #{q.id} is assigned to {usage} active/historical assessment(s). "
                f"It was safely DEACTIVATED rather than deleted to preserve test integrity.",
            )
        else:
            q.delete()
            log_admin_activity(request.user, AdminActivityLog.ActionTypes.QUESTION_DELETED, f"Deleted MCQ #{question_id} permanently", request=request)
            messages.success(request, f"Question #{question_id} was deleted permanently.")
    elif q_type == "coding":
        cq = get_object_or_404(CodingQuestion, pk=question_id)
        usage = cq.usage_count
        if usage > 0:
            cq.is_active = False
            cq.save(update_fields=["is_active"])
            log_admin_activity(request.user, AdminActivityLog.ActionTypes.QUESTION_DELETED, f"Soft-deactivated in-use Coding Challenge '{cq.title}' ({usage} assessments)", request=request)
            messages.warning(
                request,
                f"Coding Challenge '{cq.title}' is assigned to {usage} active/historical assessment(s). "
                f"It was safely DEACTIVATED rather than deleted to preserve candidate test integrity.",
            )
        else:
            cq.delete()
            log_admin_activity(request.user, AdminActivityLog.ActionTypes.QUESTION_DELETED, f"Deleted Coding Challenge '{cq.title}' permanently", request=request)
            messages.success(request, f"Coding Challenge '{cq.title}' was deleted permanently.")
    else:
        messages.error(request, "Invalid question type.")

    return redirect(request.META.get("HTTP_REFERER") or "dashboard:admin_questions")


@admin_required
@require_POST
def admin_questions_bulk_action(request):
    """Execute bulk activate, deactivate, or approve actions on selected questions."""
    action = request.POST.get("bulk_action", "").strip()
    selected_items = request.POST.getlist("selected_questions")

    if not action or not selected_items:
        messages.warning(request, "Please select at least one question and an action.")
        return redirect("dashboard:admin_questions")

    mcq_ids = []
    coding_ids = []

    for item in selected_items:
        if item.startswith("mcq_"):
            try:
                mcq_ids.append(int(item.replace("mcq_", "")))
            except ValueError:
                pass
        elif item.startswith("coding_"):
            try:
                coding_ids.append(int(item.replace("coding_", "")))
            except ValueError:
                pass

    updated_count = 0
    if action == "activate":
        if mcq_ids:
            updated_count += Question.objects.filter(id__in=mcq_ids).update(is_active=True)
        if coding_ids:
            updated_count += CodingQuestion.objects.filter(id__in=coding_ids).update(is_active=True)
        log_admin_activity(request.user, AdminActivityLog.ActionTypes.BULK_QUESTION_ACTION, f"Bulk activated {updated_count} question(s)", request=request)
        messages.success(request, f"Successfully activated {updated_count} question(s).")
    elif action == "deactivate":
        if mcq_ids:
            updated_count += Question.objects.filter(id__in=mcq_ids).update(is_active=False)
        if coding_ids:
            updated_count += CodingQuestion.objects.filter(id__in=coding_ids).update(is_active=False)
        log_admin_activity(request.user, AdminActivityLog.ActionTypes.BULK_QUESTION_ACTION, f"Bulk deactivated {updated_count} question(s)", request=request)
        messages.success(request, f"Successfully deactivated {updated_count} question(s).")
    elif action == "approve":
        if mcq_ids:
            updated_count += Question.objects.filter(id__in=mcq_ids).update(is_reviewed=True, is_approved=True)
        if coding_ids:
            updated_count += CodingQuestion.objects.filter(id__in=coding_ids).update(is_reviewed=True, is_approved=True)
        log_admin_activity(request.user, AdminActivityLog.ActionTypes.BULK_QUESTION_ACTION, f"Bulk approved {updated_count} question(s)", request=request)
        messages.success(request, f"Successfully approved {updated_count} question(s).")
    else:
        messages.error(request, "Unknown bulk action requested.")

    return redirect("dashboard:admin_questions")

    return redirect("dashboard:admin_questions")


# =============================================================================
# 3. PLATFORM-WIDE ASSESSMENT MANAGEMENT
# =============================================================================

@admin_required
def admin_assessments_list(request):
    """View and filter all assessments across all employers."""
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    employer_filter = request.GET.get("employer", "").strip()
    coding_filter = request.GET.get("has_coding", "").strip()

    assessments = (
        Assessment.objects.select_related("employer", "employer__employer_profile", "candidate", "group", "result")
        .order_by("-created_at")
    )

    if search_query:
        assessments = assessments.filter(
            Q(title__icontains=search_query)
            | Q(token__icontains=search_query)
            | Q(candidate__username__icontains=search_query)
            | Q(candidate__email__icontains=search_query)
            | Q(employer__username__icontains=search_query)
            | Q(employer__email__icontains=search_query)
        )
    if status_filter and status_filter in Assessment.Status.values:
        assessments = assessments.filter(status=status_filter)
    if employer_filter:
        assessments = assessments.filter(employer__username=employer_filter)
    if coding_filter == "yes":
        assessments = assessments.filter(has_coding=True)
    elif coding_filter == "no":
        assessments = assessments.filter(has_coding=False)

    employers = User.objects.filter(employer_profile__isnull=False).order_by("username")

    paginator = Paginator(assessments, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "employer_filter": employer_filter,
        "coding_filter": coding_filter,
        "status_choices": Assessment.Status.choices,
        "employers": employers,
        "total_count": paginator.count,
    }
    return render(request, "admin_portal/assessments_list.html", context)


@admin_required
def admin_assessment_detail(request, assessment_id):
    """Inspect full candidate assessment details, questions assigned, submissions, and proctoring audit."""
    assessment = get_object_or_404(
        Assessment.objects.select_related(
            "employer",
            "employer__employer_profile",
            "candidate",
            "candidate__candidate_profile",
            "group",
            "result",
        ),
        pk=assessment_id,
    )

    assigned_mcqs = assessment.questions.select_related("question").order_by("order")
    assigned_codings = assessment.coding_questions.select_related("question").order_by("order")
    answers = {a.question_id: a for a in assessment.answers.select_related("question")}
    coding_submissions = assessment.coding_submissions.select_related("question").order_by("question__id")

    log_admin_activity(request.user, AdminActivityLog.ActionTypes.ASSESSMENT_VIEWED, f"Inspected Assessment #{assessment.id} ({assessment.title})", request=request)

    mcq_details = []
    for amcq in assigned_mcqs:
        ans = answers.get(amcq.question_id)
        mcq_details.append({
            "order": amcq.order,
            "question": amcq.question,
            "answer": ans,
            "is_correct": ans.is_correct if ans else False,
            "selected_answer": ans.selected_answer if ans else "Unanswered",
        })

    context = {
        "assessment": assessment,
        "group": assessment.group,
        "result": getattr(assessment, "result", None),
        "mcq_details": mcq_details,
        "assigned_codings": assigned_codings,
        "coding_submissions": coding_submissions,
    }
    return render(request, "admin_portal/assessment_detail.html", context)


# =============================================================================
# 4. PLATFORM-WIDE CAMPAIGN MANAGEMENT
# =============================================================================

@admin_required
def admin_campaigns_list(request):
    """Admin view for all assessment campaigns across all employers."""
    search_query = request.GET.get("q", "").strip()
    employer_filter = request.GET.get("employer", "").strip()

    campaigns = (
        AssessmentGroup.objects.select_related("employer", "employer__employer_profile")
        .prefetch_related("assessments")
        .order_by("-created_at")
    )

    if search_query:
        campaigns = campaigns.filter(
            Q(title__icontains=search_query)
            | Q(employer__username__icontains=search_query)
            | Q(employer__email__icontains=search_query)
        )
    if employer_filter:
        campaigns = campaigns.filter(employer__username=employer_filter)

    employers = User.objects.filter(employer_profile__isnull=False).order_by("username")

    paginator = Paginator(campaigns, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "employer_filter": employer_filter,
        "employers": employers,
        "total_count": paginator.count,
    }
    return render(request, "admin_portal/campaigns_list.html", context)


@admin_required
def admin_campaign_detail(request, campaign_id):
    """Admin inspection view for a complete assessment campaign."""
    campaign = get_object_or_404(
        AssessmentGroup.objects.select_related("employer", "employer__employer_profile"),
        pk=campaign_id,
    )

    assessments = (
        campaign.assessments.select_related("candidate", "candidate__candidate_profile", "result")
        .order_by("-created_at")
    )

    context = {
        "campaign": campaign,
        "assessments": assessments,
        "total_assigned": assessments.count(),
        "completed_count": assessments.filter(status=Assessment.Status.COMPLETED).count(),
        "in_progress_count": assessments.filter(status=Assessment.Status.ONGOING).count(),
        "not_started_count": assessments.filter(
            status=Assessment.Status.PENDING,
            candidate_status=Assessment.CandidateStatus.NOT_STARTED,
        ).count(),
        "shortlisted_count": assessments.filter(is_shortlisted=True).count(),
    }
    return render(request, "admin_portal/campaign_detail.html", context)


# =============================================================================
# 5. PLATFORM-WIDE RESULTS & ANALYTICS
# =============================================================================

@admin_required
def admin_results_analytics(request):
    """Platform-wide assessment performance analytics, averages, distributions, and results audit."""
    employer_filter = request.GET.get("employer", "").strip()
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    results_qs = Result.objects.select_related(
        "assessment",
        "assessment__candidate",
        "assessment__candidate__candidate_profile",
        "assessment__employer",
        "assessment__employer__employer_profile",
    ).order_by("-completed_at")

    if employer_filter:
        results_qs = results_qs.filter(assessment__employer__username=employer_filter)
    if search_query:
        results_qs = results_qs.filter(
            Q(assessment__candidate__username__icontains=search_query)
            | Q(assessment__candidate__email__icontains=search_query)
            | Q(assessment__title__icontains=search_query)
        )
    if status_filter == "passed":
        results_qs = results_qs.filter(overall_score__gte=60.0)
    elif status_filter == "failed":
        results_qs = results_qs.filter(overall_score__lt=60.0)
    elif status_filter == "malpractice":
        results_qs = results_qs.filter(auto_submitted_for_malpractice=True)

    # Metrics
    total_completed = results_qs.count()
    avg_overall = results_qs.aggregate(avg=Avg("overall_score"))["avg"] or 0
    highest_score = results_qs.aggregate(m=Max("overall_score"))["m"] or 0
    lowest_score = results_qs.aggregate(m=Min("overall_score"))["m"] or 0
    avg_aptitude = results_qs.aggregate(avg=Avg("aptitude_score"))["avg"] or 0
    avg_coding = results_qs.filter(has_coding=True).aggregate(avg=Avg("coding_score"))["avg"] or 0

    passed_count = results_qs.filter(overall_score__gte=60.0).count()
    pass_rate = round((passed_count / total_completed * 100), 1) if total_completed > 0 else 0

    total_assigned_all = Assessment.objects.count()
    completed_all = Assessment.objects.filter(status=Assessment.Status.COMPLETED).count()
    completion_rate = round((completed_all / total_assigned_all * 100), 1) if total_assigned_all > 0 else 0

    employers = User.objects.filter(employer_profile__isnull=False).order_by("username")

    paginator = Paginator(results_qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "total_completed": total_completed,
        "avg_overall": round(float(avg_overall), 1),
        "highest_score": round(float(highest_score), 1),
        "lowest_score": round(float(lowest_score), 1),
        "avg_aptitude": round(float(avg_aptitude), 1),
        "avg_coding": round(float(avg_coding), 1),
        "pass_rate": pass_rate,
        "completion_rate": completion_rate,
        "employer_filter": employer_filter,
        "search_query": search_query,
        "status_filter": status_filter,
        "employers": employers,
    }
    return render(request, "admin_portal/results_analytics.html", context)


@admin_required
def admin_results_csv_export(request):
    """Export platform-wide candidate evaluation results as CSV."""
    results = (
        Result.objects.select_related(
            "assessment",
            "assessment__candidate",
            "assessment__employer",
            "assessment__employer__employer_profile",
        )
        .order_by("-completed_at")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="platform_all_results_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Candidate Name",
        "Candidate Email",
        "Employer / Company",
        "Assessment Title",
        "Status",
        "Aptitude Score",
        "Coding Score",
        "Overall Score",
        "Pass Status",
        "Violations",
        "Auto Submitted",
        "Submission Reason",
        "Completed At (IST)",
    ])

    for res in results:
        cand = res.assessment.candidate
        cand_name = cand.get_full_name() or cand.username
        emp = res.assessment.employer
        emp_company = getattr(getattr(emp, "employer_profile", None), "company", emp.username)
        passed = "PASSED" if float(res.overall_score) >= 60.0 else "FAILED"

        writer.writerow([
            cand_name,
            cand.email,
            emp_company,
            res.assessment.title,
            res.assessment.get_status_display(),
            f"{res.aptitude_score}%",
            f"{res.coding_score}%" if (res.has_coding or res.assessment.has_coding) else "N/A",
            f"{res.overall_score}%",
            passed,
            f"{res.violation_count}/3",
            "Yes" if res.auto_submitted_for_malpractice else "No",
            res.submission_reason or "Standard completion",
            res.completed_at.strftime("%Y-%m-%d %I:%M %p") if res.completed_at else "N/A",
        ])

    return response


# =============================================================================
# 6. PLATFORM-WIDE PROCTORING / MALPRACTICE AUDIT
# =============================================================================

@admin_required
def admin_proctoring_dashboard(request):
    """Platform-wide proctoring audit log with violation breakdowns and malpractice filters."""
    flagged_filter = request.GET.get("flagged", "").strip().lower()
    auto_sub_filter = request.GET.get("auto_submitted", "").strip().lower()
    warning_count_filter = request.GET.get("warnings", "").strip()
    employer_filter = request.GET.get("employer", "").strip()
    search_query = request.GET.get("q", "").strip()

    assessments_qs = (
        Assessment.objects.select_related("employer", "employer__employer_profile", "candidate", "group")
        .filter(status__in=[Assessment.Status.ONGOING, Assessment.Status.COMPLETED, Assessment.Status.EXPIRED])
        .order_by("-last_violation_at", "-created_at")
    )

    if flagged_filter == "yes":
        assessments_qs = assessments_qs.filter(Q(violation_count__gt=0) | Q(auto_submitted_for_malpractice=True))
    elif flagged_filter == "no":
        assessments_qs = assessments_qs.filter(violation_count=0, auto_submitted_for_malpractice=False)

    if auto_sub_filter == "yes":
        assessments_qs = assessments_qs.filter(auto_submitted_for_malpractice=True)
    elif auto_sub_filter == "no":
        assessments_qs = assessments_qs.filter(auto_submitted_for_malpractice=False)

    if warning_count_filter:
        try:
            min_w = int(warning_count_filter)
            assessments_qs = assessments_qs.filter(violation_count__gte=min_w)
        except ValueError:
            pass

    if employer_filter:
        assessments_qs = assessments_qs.filter(employer__username=employer_filter)

    if search_query:
        assessments_qs = assessments_qs.filter(
            Q(candidate__username__icontains=search_query)
            | Q(candidate__email__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(last_violation_type__icontains=search_query)
        )

    # Stats
    total_monitored = Assessment.objects.filter(
        status__in=[Assessment.Status.ONGOING, Assessment.Status.COMPLETED, Assessment.Status.EXPIRED]
    ).count()
    total_flagged = Assessment.objects.filter(violation_count__gt=0).count()
    total_auto_submitted = Assessment.objects.filter(auto_submitted_for_malpractice=True).count()
    clean_submissions = total_monitored - total_flagged

    employers = User.objects.filter(employer_profile__isnull=False).order_by("username")

    paginator = Paginator(assessments_qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "total_monitored": total_monitored,
        "total_flagged": total_flagged,
        "total_auto_submitted": total_auto_submitted,
        "clean_submissions": clean_submissions,
        "flagged_filter": flagged_filter,
        "auto_sub_filter": auto_sub_filter,
        "warning_count_filter": warning_count_filter,
        "employer_filter": employer_filter,
        "search_query": search_query,
        "employers": employers,
    }
    return render(request, "admin_portal/proctoring_dashboard.html", context)


# =============================================================================
# 7. AI MANAGEMENT & DECISION SUPPORT GOVERNANCE
# =============================================================================

@admin_required
def admin_ai_management(request):
    """Admin oversight for AI-generated questions and AI candidate shortlisting heuristics."""
    ai_questions = Question.objects.filter(source_type=Question.SourceTypes.AI_GENERATED).order_by("-created_at")[:50]
    total_ai_mcq = Question.objects.filter(source_type=Question.SourceTypes.AI_GENERATED).count()
    approved_ai_mcq = Question.objects.filter(source_type=Question.SourceTypes.AI_GENERATED, is_approved=True).count()
    total_ai_coding = CodingQuestion.objects.filter(source_type=Question.SourceTypes.AI_GENERATED).count()
    total_shortlisted = Assessment.objects.filter(is_shortlisted=True).count()

    context = {
        "ai_questions": ai_questions,
        "total_ai_mcq": total_ai_mcq,
        "approved_ai_mcq": approved_ai_mcq,
        "total_ai_coding": total_ai_coding,
        "total_shortlisted": total_shortlisted,
    }
    return render(request, "admin_portal/ai_management.html", context)


# =============================================================================
# 8. ADMIN ACTIVITY AUDIT LOG
# =============================================================================

@admin_required
def admin_activity_logs(request):
    """View chronological, tamper-evident security audit logs of all administrative actions."""
    search_query = request.GET.get("q", "").strip()
    action_type_filter = request.GET.get("action_type", "").strip()

    logs_qs = AdminActivityLog.objects.select_related("admin_user").order_by("-created_at")

    if search_query:
        logs_qs = logs_qs.filter(
            Q(admin_user__username__icontains=search_query)
            | Q(admin_user__email__icontains=search_query)
            | Q(details__icontains=search_query)
            | Q(ip_address__icontains=search_query)
        )
    if action_type_filter and action_type_filter in AdminActivityLog.ActionTypes.values:
        logs_qs = logs_qs.filter(action_type=action_type_filter)

    paginator = Paginator(logs_qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "action_type_filter": action_type_filter,
        "action_choices": AdminActivityLog.ActionTypes.choices,
    }
    return render(request, "admin_portal/activity_logs.html", context)


# =============================================================================
# 9. PLATFORM REPORTS & CSV EXPORTS
# =============================================================================

@admin_required
def admin_reports(request):
    """Admin reports landing page with one-click dataset generators."""
    return render(request, "admin_portal/reports.html")


@admin_required
def admin_export_candidates_csv(request):
    """Export all registered candidates as CSV."""
    log_admin_activity(request.user, AdminActivityLog.ActionTypes.REPORT_GENERATED, "Exported Candidates CSV report", request=request)
    candidates = CandidateProfile.objects.select_related("user").order_by("-created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="candidates_roster_export.csv"'
    writer = csv.writer(response)
    writer.writerow(["Candidate Name", "Email", "Phone", "Education", "Experience (Years)", "Skills", "Profile Completed", "Email Verified", "Registered At"])

    for c in candidates:
        writer.writerow([
            c.user.get_full_name() or c.user.username,
            c.user.email,
            c.phone,
            c.education,
            c.experience,
            c.skills,
            "Yes" if c.profile_completed else "No",
            "Yes" if c.email_verified else "No",
            c.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])
    return response


@admin_required
def admin_export_employers_csv(request):
    """Export all registered employers as CSV."""
    log_admin_activity(request.user, AdminActivityLog.ActionTypes.REPORT_GENERATED, "Exported Employers CSV report", request=request)
    employers = EmployerProfile.objects.select_related("user").order_by("-created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="employers_directory_export.csv"'
    writer = csv.writer(response)
    writer.writerow(["Company Name", "Contact Username", "Email", "Campaigns Count", "Assessments Assigned", "Account Status", "Registered At"])

    for emp in employers:
        writer.writerow([
            emp.company or "Independent",
            emp.user.username,
            emp.user.email,
            emp.user.assessment_groups.count(),
            emp.user.assessments_created.count(),
            "Active" if emp.user.is_active else "Suspended",
            emp.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])
    return response


@admin_required
def admin_export_assessments_csv(request):
    """Export all assessments across all employers as CSV."""
    log_admin_activity(request.user, AdminActivityLog.ActionTypes.REPORT_GENERATED, "Exported Assessments CSV report", request=request)
    assessments = Assessment.objects.select_related("employer", "candidate", "group", "result").order_by("-created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="assessments_master_export.csv"'
    writer = csv.writer(response)
    writer.writerow(["Assessment ID", "Title", "Employer", "Candidate", "Candidate Email", "Status", "Candidate Attendance", "Overall Score", "Violations", "Start Time (IST)", "Expire Time (IST)"])

    for ass in assessments:
        score_val = f"{ass.result.overall_score}%" if getattr(ass, "result", None) else "N/A"
        writer.writerow([
            ass.id,
            ass.title,
            ass.employer.username,
            ass.candidate.get_full_name() or ass.candidate.username,
            ass.candidate.email,
            ass.get_status_display(),
            ass.get_candidate_status_display(),
            score_val,
            f"{ass.violation_count}/3",
            ass.start_time.strftime("%Y-%m-%d %I:%M %p"),
            ass.expire_time.strftime("%Y-%m-%d %I:%M %p"),
        ])
    return response


@admin_required
def admin_export_questions_csv(request):
    """Export complete question bank inventory as CSV."""
    log_admin_activity(request.user, AdminActivityLog.ActionTypes.REPORT_GENERATED, "Exported Question Bank CSV report", request=request)
    mcqs = Question.objects.all().order_by("section", "id")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="question_bank_inventory_export.csv"'
    writer = csv.writer(response)
    writer.writerow(["ID", "Type", "Section / Domain", "Category", "Difficulty", "Question Text", "Correct Answer", "Explanation", "Provenance Source", "AI Provider", "Active Status", "Usage Count"])

    for q in mcqs:
        writer.writerow([
            q.id,
            "MCQ Aptitude",
            q.get_section_display(),
            q.category or q.get_section_display(),
            q.get_difficulty_display(),
            q.question_text,
            q.correct_answer,
            q.explanation,
            q.get_source_type_display(),
            q.ai_provider or "N/A",
            "Active" if q.is_active else "Inactive",
            q.usage_count,
        ])
    return response


@admin_required
def admin_export_proctoring_csv(request):
    """Export all proctoring violation logs as CSV."""
    log_admin_activity(request.user, AdminActivityLog.ActionTypes.REPORT_GENERATED, "Exported Proctoring CSV report", request=request)
    assessments = Assessment.objects.select_related("employer", "candidate").filter(
        status__in=[Assessment.Status.ONGOING, Assessment.Status.COMPLETED, Assessment.Status.EXPIRED]
    ).order_by("-last_violation_at", "-created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="proctoring_telemetry_export.csv"'
    writer = csv.writer(response)
    writer.writerow(["Candidate Name", "Candidate Email", "Assessment Title", "Employer", "Violation Count", "Last Violation Type", "Auto-Submitted", "Submission Reason", "Last Violation Time"])

    for ass in assessments:
        writer.writerow([
            ass.candidate.get_full_name() or ass.candidate.username,
            ass.candidate.email,
            ass.title,
            ass.employer.username,
            f"{ass.violation_count}/3",
            ass.last_violation_type or "None",
            "Yes" if ass.auto_submitted_for_malpractice else "No",
            ass.submission_reason or "Standard completion",
            ass.last_violation_at.strftime("%Y-%m-%d %H:%M:%S") if ass.last_violation_at else "N/A",
        ])
    return response


# =============================================================================
# 10. CANDIDATE & EMPLOYER DIRECTORY MANAGEMENT
# =============================================================================

@admin_required
def admin_candidates_list(request):
    """Admin view of all registered candidates across the platform."""
    search_query = request.GET.get("q", "").strip()
    candidates = CandidateProfile.objects.select_related("user").order_by("-created_at")

    if search_query:
        candidates = candidates.filter(
            Q(user__username__icontains=search_query)
            | Q(user__email__icontains=search_query)
            | Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(education__icontains=search_query)
            | Q(skills__icontains=search_query)
            | Q(phone__icontains=search_query)
        )

    paginator = Paginator(candidates, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
    }
    return render(request, "admin_portal/candidates_list.html", context)


@admin_required
def admin_employers_list(request):
    """Admin view of all registered employers across the platform with suspension toggles."""
    search_query = request.GET.get("q", "").strip()
    employers = EmployerProfile.objects.select_related("user").order_by("-created_at")

    if search_query:
        employers = employers.filter(
            Q(user__username__icontains=search_query)
            | Q(user__email__icontains=search_query)
            | Q(company__icontains=search_query)
        )

    paginator = Paginator(employers, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
    }
    return render(request, "admin_portal/employers_list.html", context)


@admin_required
@require_POST
def admin_employer_toggle_active(request, user_id):
    """Suspend or reactivate an employer account."""
    emp_user = get_object_or_404(User, pk=user_id)
    emp_user.is_active = not emp_user.is_active
    emp_user.save(update_fields=["is_active"])

    status_label = "activated" if emp_user.is_active else "suspended"
    log_admin_activity(request.user, AdminActivityLog.ActionTypes.EMPLOYER_STATUS_CHANGED, f"Employer {emp_user.username} {status_label}", request=request)
    messages.success(request, f"Employer account '{emp_user.username}' has been {status_label}.")
    return redirect("dashboard:admin_employers_list")

