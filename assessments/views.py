"""Views for employer assessment management and candidate test taking."""

import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST



from accounts.decorators import candidate_required, employer_required
from accounts.models import CandidateProfile
from assessments.code_executor import get_code_executor
from assessments.coding_bank import ensure_coding_bank_seeded
from assessments.email_service import send_assessment_invitation
from assessments.forms import AssessmentCreateForm
from assessments.models import (
    Answer,
    Assessment,
    AssessmentCodingQuestion,
    AssessmentQuestion,
    CodingQuestion,
    CodingSubmission,
    CodingTestCase,
    Question,
)
from assessments.question_bank import ensure_question_bank_seeded
from assessments.services import expire_past_due_assessments, grade_and_complete_assessment



# ---------------------------------------------------------------------------
# Employer Assessment Views
# ---------------------------------------------------------------------------

@employer_required
def employer_assessment_create(request):
    """Create and configure a new assessment for a registered candidate."""
    # Ensure default question banks are seeded
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

    # Provide question bank totals for the interactive UI counters
    logical_bank_count = Question.objects.filter(section=Question.Sections.LOGICAL).count()
    quant_bank_count = Question.objects.filter(section=Question.Sections.QUANTITATIVE).count()
    tech_bank_count = Question.objects.filter(section=Question.Sections.TECHNICAL).count()
    coding_bank_count = CodingQuestion.objects.count()

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
        include_coding = form.cleaned_data.get("include_coding", False)
        coding_count = form.cleaned_data.get("coding_count") or 0

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
            has_coding=include_coding,
        )

        # Assign randomly selected unique questions in order
        order_index = 1
        questions_to_link = []

        if "LOGICAL" in sections and logical_count > 0:
            logical_qs = Question.objects.filter(section=Question.Sections.LOGICAL).order_by("?")[:logical_count]
            for q in logical_qs:
                questions_to_link.append(AssessmentQuestion(assessment=assessment, question=q, order=order_index))
                order_index += 1

        if "QUANTITATIVE" in sections and quant_count > 0:
            quant_qs = Question.objects.filter(section=Question.Sections.QUANTITATIVE).order_by("?")[:quant_count]
            for q in quant_qs:
                questions_to_link.append(AssessmentQuestion(assessment=assessment, question=q, order=order_index))
                order_index += 1

        if "TECHNICAL" in sections and technical_count > 0:
            tech_qs = Question.objects.filter(section=Question.Sections.TECHNICAL).order_by("?")[:technical_count]
            for q in tech_qs:
                questions_to_link.append(AssessmentQuestion(assessment=assessment, question=q, order=order_index))
                order_index += 1

        AssessmentQuestion.objects.bulk_create(questions_to_link)

        # Assign Coding Questions if coding is enabled
        if include_coding and coding_count > 0:
            coding_qs = list(CodingQuestion.objects.order_by("?")[:coding_count])
            coding_to_link = []
            for c_idx, cq in enumerate(coding_qs, start=1):
                coding_to_link.append(AssessmentCodingQuestion(assessment=assessment, question=cq, order=c_idx))
            AssessmentCodingQuestion.objects.bulk_create(coding_to_link)

            # Initialize baseline CodingSubmission records with clean empty source code
            for cq in coding_qs:
                CodingSubmission.objects.get_or_create(
                    assessment=assessment,
                    question=cq,
                    defaults={
                        "language": "python",
                        "source_code": "",
                        "total_test_cases": cq.test_cases.count(),
                    },
                )


        # Sync Assessment to Firestore
        try:
            from services.firebase_service import sync_assessment_to_firestore
            q_ids = [aq.question_id for aq in questions_to_link]
            sync_assessment_to_firestore(assessment, q_ids)
        except Exception:
            pass

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
        "coding_bank_count": coding_bank_count,
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