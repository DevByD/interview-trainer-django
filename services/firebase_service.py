"""Firebase Firestore repository and synchronization service.

Provides high-level CRUD and query functions for:
- candidates (Candidate user details & profile)
- employers (Employer user details & company profile)
- questions (Question bank items)
- assessments (Assessment configurations, tokens, schedule, and statuses)
- answers (Candidate submitted answers)
- results (Automated grading breakdowns and final percentages)
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from services.firebase_config import get_firestore_client, is_firebase_available

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers for serialization
# ---------------------------------------------------------------------------
def _format_timestamp(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Candidates Collection
# ---------------------------------------------------------------------------
def sync_candidate_to_firestore(user: Any, profile: Any) -> Optional[str]:
    """Persist or update a Candidate in the 'candidates' Firestore collection."""
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc_id = str(user.id)
        doc_ref = db.collection("candidates").document(doc_id)
        data = {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "phone": getattr(profile, "phone", "") or "",
            "education": getattr(profile, "education", "") or "",
            "skills": getattr(profile, "skills", "") or "",
            "experience": getattr(profile, "experience", 0) or 0,
            "resume_url": getattr(profile.resume, "url", "") if getattr(profile, "resume", None) else "",
            "profile_completed": getattr(profile, "profile_completed", False),
            "email_verified": getattr(profile, "email_verified", False),
            "updated_at": _format_timestamp(datetime.utcnow()),
        }
        if hasattr(profile, "created_at") and profile.created_at:
            data["created_at"] = _format_timestamp(profile.created_at)

        doc_ref.set(data, merge=True)
        return doc_id
    except Exception as e:
        logger.warning("Failed to sync candidate %s to Firestore: %s", getattr(user, "username", ""), e)
        return None


def get_candidate_from_firestore(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve candidate document by user_id from Firestore."""
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc = db.collection("candidates").document(str(user_id)).get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        logger.warning("Failed to get candidate %s from Firestore: %s", user_id, e)
    return None


def list_candidates_from_firestore() -> List[Dict[str, Any]]:
    """List all candidate profiles from Firestore."""
    db = get_firestore_client()
    if not db:
        return []

    try:
        docs = db.collection("candidates").order_by("username").stream()
        return [d.to_dict() for d in docs]
    except Exception as e:
        logger.warning("Failed to list candidates from Firestore: %s", e)
        return []


# ---------------------------------------------------------------------------
# Employers Collection
# ---------------------------------------------------------------------------
def sync_employer_to_firestore(user: Any, profile: Any) -> Optional[str]:
    """Persist or update an Employer in the 'employers' Firestore collection."""
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc_id = str(user.id)
        doc_ref = db.collection("employers").document(doc_id)
        data = {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "company": getattr(profile, "company", "") or "",
            "updated_at": _format_timestamp(datetime.utcnow()),
        }
        if hasattr(profile, "created_at") and profile.created_at:
            data["created_at"] = _format_timestamp(profile.created_at)

        doc_ref.set(data, merge=True)
        return doc_id
    except Exception as e:
        logger.warning("Failed to sync employer %s to Firestore: %s", getattr(user, "username", ""), e)
        return None


def get_employer_from_firestore(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve employer document by user_id from Firestore."""
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc = db.collection("employers").document(str(user_id)).get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        logger.warning("Failed to get employer %s from Firestore: %s", user_id, e)
    return None


# ---------------------------------------------------------------------------
# Questions Collection
# ---------------------------------------------------------------------------
def sync_question_to_firestore(question: Any) -> Optional[str]:
    """Persist a Question bank entry in the 'questions' Firestore collection."""
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc_id = str(question.id)
        doc_ref = db.collection("questions").document(doc_id)
        data = {
            "question_id": question.id,
            "section": question.section,
            "question_text": question.question_text,
            "option_a": question.option_a,
            "option_b": question.option_b,
            "option_c": question.option_c,
            "option_d": question.option_d,
            "correct_answer": question.correct_answer,
            "difficulty": question.difficulty,
            "created_at": _format_timestamp(getattr(question, "created_at", None)),
        }
        doc_ref.set(data, merge=True)
        return doc_id
    except Exception as e:
        logger.warning("Failed to sync question %s to Firestore: %s", getattr(question, "id", ""), e)
        return None


def bulk_sync_questions_to_firestore(questions: List[Any]) -> int:
    """Bulk synchronize question list to Firestore."""
    count = 0
    for q in questions:
        if sync_question_to_firestore(q):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Assessments Collection
# ---------------------------------------------------------------------------
def sync_assessment_to_firestore(assessment: Any, question_ids: Optional[List[int]] = None) -> Optional[str]:
    """Persist an Assessment document in the 'assessments' Firestore collection."""
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc_id = str(assessment.id)
        doc_ref = db.collection("assessments").document(doc_id)

        if question_ids is None and hasattr(assessment, "questions"):
            question_ids = list(assessment.questions.values_list("question_id", flat=True))

        data = {
            "assessment_id": assessment.id,
            "token": assessment.token,
            "title": assessment.title,
            "employer_id": assessment.employer_id,
            "employer_username": getattr(assessment.employer, "username", ""),
            "candidate_id": assessment.candidate_id,
            "candidate_username": getattr(assessment.candidate, "username", ""),
            "start_time": _format_timestamp(assessment.start_time),
            "expire_time": _format_timestamp(assessment.expire_time),
            "duration_minutes": assessment.duration_minutes,
            "status": assessment.status,
            "candidate_status": assessment.candidate_status,
            "question_ids": question_ids or [],
            "updated_at": _format_timestamp(datetime.utcnow()),
        }
        if hasattr(assessment, "created_at") and assessment.created_at:
            data["created_at"] = _format_timestamp(assessment.created_at)

        doc_ref.set(data, merge=True)
        return doc_id
    except Exception as e:
        logger.warning("Failed to sync assessment %s to Firestore: %s", getattr(assessment, "id", ""), e)
        return None


def update_assessment_status_in_firestore(
    assessment_id: int,
    status: str,
    candidate_status: Optional[str] = None,
) -> bool:
    """Update assessment lifecycle and candidate status in Firestore."""
    db = get_firestore_client()
    if not db:
        return False

    try:
        doc_ref = db.collection("assessments").document(str(assessment_id))
        update_data = {
            "status": status,
            "updated_at": _format_timestamp(datetime.utcnow()),
        }
        if candidate_status is not None:
            update_data["candidate_status"] = candidate_status
        doc_ref.update(update_data)
        return True
    except Exception as e:
        logger.warning("Failed to update assessment status in Firestore: %s", e)
        return False


def get_assessment_from_firestore_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Retrieve an assessment by its unique token from Firestore."""
    db = get_firestore_client()
    if not db:
        return None

    try:
        query = db.collection("assessments").where("token", "==", token).limit(1)
        results = list(query.stream())
        if results:
            return results[0].to_dict()
    except Exception as e:
        logger.warning("Failed to find assessment by token in Firestore: %s", e)
    return None


# ---------------------------------------------------------------------------
# Answers Collection
# ---------------------------------------------------------------------------
def sync_answer_to_firestore(
    assessment_id: int,
    question_id: int,
    selected_answer: str,
    is_correct: bool,
) -> Optional[str]:
    """Persist a candidate's answer for an assessment question in Firestore."""
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc_id = f"{assessment_id}_{question_id}"
        doc_ref = db.collection("answers").document(doc_id)
        data = {
            "assessment_id": assessment_id,
            "question_id": question_id,
            "selected_answer": selected_answer,
            "is_correct": is_correct,
            "submitted_at": _format_timestamp(datetime.utcnow()),
        }
        doc_ref.set(data, merge=True)
        return doc_id
    except Exception as e:
        logger.warning("Failed to sync answer to Firestore: %s", e)
        return None


# ---------------------------------------------------------------------------
# Results Collection
# ---------------------------------------------------------------------------
def sync_result_to_firestore(result: Any) -> Optional[str]:
    """Persist a graded Result in the 'results' Firestore collection."""
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc_id = str(result.assessment_id)
        doc_ref = db.collection("results").document(doc_id)
        data = {
            "result_id": getattr(result, "id", None),
            "assessment_id": result.assessment_id,
            "assessment_title": getattr(result.assessment, "title", ""),
            "candidate_id": getattr(result.assessment, "candidate_id", None),
            "employer_id": getattr(result.assessment, "employer_id", None),
            "logical_correct": result.logical_correct,
            "logical_total": result.logical_total,
            "quant_correct": result.quant_correct,
            "quant_total": result.quant_total,
            "technical_correct": result.technical_correct,
            "technical_total": result.technical_total,
            "total_correct": result.total_correct,
            "total_questions": result.total_questions,
            "percentage": float(result.percentage),
            "passed": result.passed,
            "completed_at": _format_timestamp(result.completed_at),
            "synced_at": _format_timestamp(datetime.utcnow()),
        }
        doc_ref.set(data, merge=True)
        return doc_id
    except Exception as e:
        logger.warning("Failed to sync result to Firestore: %s", e)
        return None


def get_result_from_firestore(assessment_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve result for an assessment from Firestore."""
    db = get_firestore_client()
    if not db:
        return None

    try:
        doc = db.collection("results").document(str(assessment_id)).get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        logger.warning("Failed to get result from Firestore: %s", e)
    return None
