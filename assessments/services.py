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
    count = past_due_qs.update(
        status=Assessment.Status.EXPIRED,
        candidate_status=Assessment.CandidateStatus.NOT_ATTENDED,
    )
    if count > 0:
        logger.info("Expired %d past due assessment(s).", count)
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
        percentage = round(Decimal(total_correct) / Decimal(total_questions) * Decimal("100.00"), 2)
    else:
        percentage = Decimal("0.00")

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
            "percentage": percentage,
            "completed_at": timezone.now(),
        },
    )

    assessment.status = Assessment.Status.COMPLETED
    assessment.candidate_status = Assessment.CandidateStatus.ATTENDED
    assessment.save(update_fields=["status", "candidate_status", "updated_at"])

    return result
