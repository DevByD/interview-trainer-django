"""Core domain services for assessments (grading, expiration, question assignment)."""

import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from assessments.models import Answer, Assessment, AssessmentQuestion, Question
from results.models import Result

logger = logging.getLogger(__name__)


def expire_past_due_assessments() -> int:
    """Find assessments past their expire_time that were not completed and mark them EXPIRED / NOT_ATTENDED.

    Completed assessments are never modified.
    Returns the number of assessments expired in this run.
    """
    now = timezone.now()
    past_due_qs = Assessment.objects.filter(
        status__in=[Assessment.Status.PENDING, Assessment.Status.ONGOING],
        expire_time__lt=now,
    )
    past_due_ids = list(past_due_qs.values_list("id", flat=True))
    count = past_due_qs.update(
        status=Assessment.Status.EXPIRED,
        candidate_status=Assessment.CandidateStatus.NOT_ATTENDED,
    )
    if count > 0:
        logger.info("Expired %d past due assessment(s).", count)
        try:
            from services.firebase_service import update_assessment_status_in_firestore
            for a_id in past_due_ids:
                update_assessment_status_in_firestore(
                    a_id, Assessment.Status.EXPIRED, Assessment.CandidateStatus.NOT_ATTENDED
                )
        except Exception as e:
            logger.warning("Failed to update expired assessments in Firestore: %s", e)

    return count



@transaction.atomic
def grade_and_complete_assessment(assessment: Assessment, raw_answers: dict[int | str, str]) -> Result:
    """Grade submitted answers, create/update Answer records, record Result, and mark assessment COMPLETED.

    raw_answers is a mapping of question_id (int or str) -> selected_option ('A', 'B', 'C', 'D').
    """
    # Lock assessment record to prevent concurrent duplicate grading
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)

    if assessment.status == Assessment.Status.COMPLETED and hasattr(assessment, "result"):
        return assessment.result

    assessment_questions = (
        AssessmentQuestion.objects.filter(assessment=assessment)
        .select_related("question")
        .order_by("order", "id")
    )

    logical_correct = 0
    logical_total = 0
    quant_correct = 0
    quant_total = 0
    technical_correct = 0
    technical_total = 0

    answers_to_create = []

    # Clean map with int keys
    cleaned_answers: dict[int, str] = {}
    for q_id_key, val in raw_answers.items():
        try:
            cleaned_answers[int(q_id_key)] = str(val).strip().upper()
        except (ValueError, TypeError):
            continue

    # Delete any prior partial answer records for this assessment
    Answer.objects.filter(assessment=assessment).delete()

    for aq in assessment_questions:
        q = aq.question
        section = q.section

        if section == Question.Sections.LOGICAL:
            logical_total += 1
        elif section == Question.Sections.QUANTITATIVE:
            quant_total += 1
        elif section == Question.Sections.TECHNICAL:
            technical_total += 1

        selected_opt = cleaned_answers.get(q.id, "")
        if selected_opt in ("A", "B", "C", "D"):
            is_corr = (selected_opt == q.correct_answer)
            if is_corr:
                if section == Question.Sections.LOGICAL:
                    logical_correct += 1
                elif section == Question.Sections.QUANTITATIVE:
                    quant_correct += 1
                elif section == Question.Sections.TECHNICAL:
                    technical_correct += 1

            answers_to_create.append(
                Answer(
                    assessment=assessment,
                    question=q,
                    selected_answer=selected_opt,
                    is_correct=is_corr,
                )
            )

    if answers_to_create:
        Answer.objects.bulk_create(answers_to_create)

    total_correct = logical_correct + quant_correct + technical_correct
    total_questions = logical_total + quant_total + technical_total

    if total_questions > 0:
        aptitude_percentage = round(Decimal(total_correct) / Decimal(total_questions) * Decimal("100.00"), 2)
    else:
        aptitude_percentage = Decimal("0.00")

    # Coding scoring
    has_coding = getattr(assessment, "has_coding", False)
    coding_score = Decimal("0.00")
    overall_score = aptitude_percentage

    if has_coding:
        assigned_coding = assessment.coding_questions.select_related("question").all()
        total_coding_q = assigned_coding.count()
        if total_coding_q > 0:
            coding_scores_sum = Decimal("0.00")
            for acq in assigned_coding:
                submission = assessment.coding_submissions.filter(question=acq.question).first()
                if submission and submission.total_test_cases > 0:
                    prob_pct = Decimal(str(submission.score)) if submission.score else Decimal(str(round(submission.passed_test_cases / submission.total_test_cases * 100.0, 2)))
                    coding_scores_sum += prob_pct
            coding_score = round(coding_scores_sum / Decimal(total_coding_q), 2)
            if total_questions > 0:
                overall_score = round((aptitude_percentage + coding_score) / Decimal("2.0"), 2)
            else:
                overall_score = coding_score


    sub_reason = assessment.submission_reason
    if not sub_reason:
        if assessment.auto_submitted_for_malpractice:
            sub_reason = "Assessment automatically submitted after 3 proctoring violations (fullscreen exit / unauthorized activity)."
        else:
            sub_reason = "Standard candidate completion"

    result, _ = Result.objects.update_or_create(
        assessment=assessment,
        defaults={
            "logical_correct": logical_correct,
            "logical_total": logical_total,
            "quant_correct": quant_correct,
            "quant_total": quant_total,
            "technical_correct": technical_correct,
            "technical_total": technical_total,
            "total_correct": total_correct,
            "total_questions": total_questions,
            "percentage": overall_score,
            "has_coding": has_coding,
            "aptitude_score": aptitude_percentage,
            "coding_score": coding_score,
            "overall_score": overall_score,
            "violation_count": assessment.violation_count,
            "auto_submitted_for_malpractice": assessment.auto_submitted_for_malpractice,
            "submission_reason": sub_reason,
            "completed_at": timezone.now(),
        },
    )

    assessment.status = Assessment.Status.COMPLETED
    assessment.candidate_status = Assessment.CandidateStatus.ATTENDED
    assessment.submission_reason = sub_reason
    assessment.save(update_fields=["status", "candidate_status", "submission_reason", "updated_at"])




    # Synchronize to Firestore
    try:
        from services.firebase_service import (
            sync_answer_to_firestore,
            sync_assessment_to_firestore,
            sync_result_to_firestore,
        )
        sync_result_to_firestore(result)
        sync_assessment_to_firestore(assessment)
        for ans in answers_to_create:
            sync_answer_to_firestore(
                assessment.id, ans.question_id, ans.selected_answer, ans.is_correct
            )
    except Exception as e:
        logger.warning("Firestore synchronization skipped during assessment completion: %s", e)

    return result