"""AI-Assisted Candidate Shortlisting & Decision-Support Service.

Analyzes completed candidate assessments based strictly on legitimate,
measurable evaluation data:
- Overall score and passing threshold
- Aptitude domain breakdown (Logical, Quantitative, Technical)
- Coding challenge performance and test case execution rates
- Proctoring & test integrity record (violations, malpractice flags, auto-submission)
- Explicit candidate professional profile metadata (skills, experience years) where provided

Guiding Principles:
1. Decision Support Only: AI recommendations are advisory to assist human recruiters.
2. Fairness & Objectivity: Recommendations are never based on or inferred from protected characteristics.
3. Truthfulness: If data is missing or incomplete, the service explicitly states so rather than inventing it.
"""

import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from django.utils import timezone

from assessments.ai_generator import call_gemini_api, clean_json_response
from assessments.models import Assessment, CodingSubmission

logger = logging.getLogger(__name__)


def evaluate_assessment_data(assessment: Assessment) -> Dict[str, Any]:
    """Extract and validate all legitimate metrics for a candidate assessment."""
    result = getattr(assessment, "result", None)
    cand = assessment.candidate
    cand_profile = getattr(cand, "candidate_profile", None)

    # Base candidate data
    cand_name = cand.get_full_name() or cand.username
    cand_email = cand.email
    skills_str = cand_profile.skills if (cand_profile and cand_profile.skills) else "Not provided"
    experience_yrs = cand_profile.experience if (cand_profile and cand_profile.experience is not None) else None

    # Status check
    is_completed = (assessment.status == Assessment.Status.COMPLETED)
    violation_count = assessment.violation_count or 0
    malpractice_flagged = bool(assessment.malpractice_status or assessment.auto_submitted_for_malpractice)
    submission_reason = assessment.submission_reason or ("Standard completion" if is_completed else "Not completed")

    has_coding = bool(assessment.has_coding or (result and result.has_coding))

    # Score metrics
    if result:
        if has_coding:
            overall_score = float(result.overall_score if result.overall_score > 0 else result.percentage)
            aptitude_score = float(result.aptitude_score if result.aptitude_score > 0 else result.percentage)
            coding_score = float(result.coding_score)
        else:
            overall_score = float(result.percentage)
            aptitude_score = float(result.percentage)
            coding_score = 0.0
    else:
        overall_score = 0.0
        aptitude_score = 0.0
        coding_score = 0.0

    # Sub-domain breakdown
    logical_stats = {
        "correct": result.logical_correct if result else 0,
        "total": result.logical_total if result else 0,
    }
    quant_stats = {
        "correct": result.quant_correct if result else 0,
        "total": result.quant_total if result else 0,
    }
    tech_stats = {
        "correct": result.technical_correct if result else 0,
        "total": result.technical_total if result else 0,
    }

    # Coding submissions breakdown
    coding_subs = CodingSubmission.objects.filter(assessment=assessment).select_related("question")
    coding_problems_summary = []
    total_test_cases = 0
    passed_test_cases = 0

    for sub in coding_subs:
        total_test_cases += sub.total_test_cases
        passed_test_cases += sub.passed_test_cases
        coding_problems_summary.append({
            "title": sub.question.title,
            "category": sub.question.category,
            "difficulty": sub.question.difficulty,
            "language": sub.get_language_display(),
            "passed_test_cases": sub.passed_test_cases,
            "total_test_cases": sub.total_test_cases,
            "score": float(sub.score),
        })

    return {
        "candidate_name": cand_name,
        "candidate_email": cand_email,
        "skills": skills_str,
        "experience_years": experience_yrs,
        "is_completed": is_completed,
        "has_coding": assessment.has_coding,
        "overall_score": overall_score,
        "aptitude_score": aptitude_score,
        "coding_score": coding_score,
        "logical_stats": logical_stats,
        "quant_stats": quant_stats,
        "tech_stats": tech_stats,
        "coding_problems": coding_problems_summary,
        "total_test_cases": total_test_cases,
        "passed_test_cases": passed_test_cases,
        "violation_count": violation_count,
        "malpractice_flagged": malpractice_flagged,
        "submission_reason": submission_reason,
    }


def generate_algorithmic_recommendation(data: Dict[str, Any]) -> Dict[str, str]:
    """Generate a deterministic, legitimate data-backed recommendation."""
    if not data["is_completed"]:
        return {
            "recommendation": Assessment.AIRecommendation.PENDING,
            "reasoning": "Assessment is not yet completed by candidate. AI analysis will run once the final submission is recorded.",
        }

    overall = data["overall_score"]
    aptitude = data["aptitude_score"]
    coding = data["coding_score"]
    has_coding = data["has_coding"]
    malpractice = data["malpractice_flagged"]
    violations = data["violation_count"]
    passed_tc = data["passed_test_cases"]
    total_tc = data["total_test_cases"]

    # 1. Malpractice / Termination Flag
    if malpractice or violations >= 3:
        return {
            "recommendation": Assessment.AIRecommendation.LOW_MATCH,
            "reasoning": f"Assessment was terminated/flagged for proctoring violations ({violations} warning(s) recorded: {data['submission_reason']}). Overall score: {overall:.1f}%. Recruiter review required for integrity verification.",
        }

    # 2. Strong Match Threshold
    is_strong = False
    if has_coding:
        if overall >= 75.0 and coding >= 70.0 and aptitude >= 65.0 and violations == 0:
            is_strong = True
    else:
        if overall >= 75.0 and violations == 0:
            is_strong = True

    if is_strong:
        coding_clause = f" Excellent coding execution ({coding:.1f}% score, {passed_tc}/{total_tc} test cases passed across algorithms)." if has_coding else ""
        return {
            "recommendation": Assessment.AIRecommendation.STRONG_MATCH,
            "reasoning": f"Strong candidate based on assessment performance. Scored {overall:.1f}% overall with {aptitude:.1f}% on aptitude.{coding_clause} Clean proctoring record with 0 violations.",
        }

    # 3. Review Recommended Threshold (Moderate / Uneven performance / Minor warnings)
    is_review = False
    if overall >= 50.0:
        is_review = True
    elif has_coding and (coding >= 70.0 or aptitude >= 70.0):
        # Good in one section despite lower total
        is_review = True
    elif violations in (1, 2):
        is_review = True

    if is_review:
        reasons = []
        if has_coding:
            if coding < 50.0:
                reasons.append(f"lower coding score ({coding:.1f}%, {passed_tc}/{total_tc} test cases)")
            elif aptitude < 50.0:
                reasons.append(f"lower aptitude score ({aptitude:.1f}%)")
            else:
                reasons.append(f"balanced performance (Aptitude: {aptitude:.1f}%, Coding: {coding:.1f}%)")
        else:
            reasons.append(f"moderate aptitude score ({aptitude:.1f}%)")

        if violations > 0:
            reasons.append(f"{violations} proctoring warning(s) noted")

        reason_str = ", ".join(reasons)
        return {
            "recommendation": Assessment.AIRecommendation.REVIEW_RECOMMENDED,
            "reasoning": f"Employer review recommended. Overall score: {overall:.1f}% ({reason_str}). Candidate demonstrated competence in key sections.",
        }

    # 4. Low Match Threshold (< 50%)
    return {
        "recommendation": Assessment.AIRecommendation.LOW_MATCH,
        "reasoning": f"Lower match based on assessment outcome. Scored {overall:.1f}% overall (Aptitude: {aptitude:.1f}%" + (f", Coding: {coding:.1f}% with {passed_tc}/{total_tc} test cases passed" if has_coding else "") + "). Did not meet baseline performance thresholds.",
    }


def analyze_assessment_with_ai(assessment: Assessment) -> Dict[str, Any]:
    """Analyze a single assessment and update its AI recommendation fields."""
    data = evaluate_assessment_data(assessment)

    # First generate the deterministic baseline recommendation
    algo_result = generate_algorithmic_recommendation(data)
    recommendation = algo_result["recommendation"]
    reasoning = algo_result["reasoning"]

    # If completed and Gemini is configured, invoke LLM for high-fidelity recruiter rationale
    if data["is_completed"]:
        try:
            prompt = f"""You are an expert technical recruiting decision-support AI.
Analyze this candidate's assessment performance and provide an objective evaluation.

ASSESSMENT DATA:
- Candidate Name: {data['candidate_name']}
- Overall Score: {data['overall_score']}%
- Aptitude Score: {data['aptitude_score']}%
- Logical Reasoning: {data['logical_stats']['correct']}/{data['logical_stats']['total']}
- Quantitative Aptitude: {data['quant_stats']['correct']}/{data['quant_stats']['total']}
- Technical Aptitude: {data['tech_stats']['correct']}/{data['tech_stats']['total']}
- Has Coding Section: {data['has_coding']}
- Coding Score: {data['coding_score']}%
- Coding Test Cases: {data['passed_test_cases']}/{data['total_test_cases']} passed
- Proctoring Violations: {data['violation_count']}
- Malpractice / Auto-Submitted: {data['malpractice_flagged']}
- Submission Note: {data['submission_reason']}

RULES:
1. Recommendation MUST be one of: "STRONG_MATCH", "REVIEW_RECOMMENDED", "LOW_MATCH".
2. Base reasoning purely on the provided scores, coding pass rates, and proctoring.
3. NEVER invent or assume unlisted skills or attributes.
4. Keep reasoning between 2 and 4 sentences.

Respond in JSON format:
{{
  "recommendation": "STRONG_MATCH | REVIEW_RECOMMENDED | LOW_MATCH",
  "reasoning": "Clear, objective reasoning text"
}}
"""
            llm_response = call_gemini_api(prompt, system_instruction="You are an ethical AI hiring assistant providing decision support based solely on assessment data.")
            if llm_response:
                parsed = clean_json_response(llm_response)
                if isinstance(parsed, dict) and parsed.get("recommendation") in Assessment.AIRecommendation.values:
                    recommendation = parsed.get("recommendation")
                    if parsed.get("reasoning"):
                        reasoning = parsed.get("reasoning").strip()
        except Exception as exc:
            logger.debug("AI Shortlist LLM enhancement notice: %s. Using algorithmic reasoning.", exc)

    # Persist decision support recommendation
    assessment.ai_recommendation = recommendation
    assessment.ai_reasoning = reasoning
    assessment.ai_analyzed_at = timezone.now()
    assessment.save(update_fields=["ai_recommendation", "ai_reasoning", "ai_analyzed_at"])

    return {
        "assessment_id": assessment.id,
        "candidate_id": assessment.candidate_id,
        "candidate_name": data["candidate_name"],
        "recommendation": recommendation,
        "recommendation_display": assessment.get_ai_recommendation_display(),
        "reasoning": reasoning,
        "overall_score": data["overall_score"],
        "coding_score": data["coding_score"],
        "aptitude_score": data["aptitude_score"],
        "violation_count": data["violation_count"],
        "is_shortlisted": assessment.is_shortlisted,
    }


def analyze_campaign_assessments(assessments_qs) -> Dict[str, Any]:
    """Run AI shortlisting evaluation across a collection of assessments."""
    results = []
    counts = {
        "STRONG_MATCH": 0,
        "REVIEW_RECOMMENDED": 0,
        "LOW_MATCH": 0,
        "PENDING": 0,
        "total_analyzed": 0,
    }

    for assessment in assessments_qs:
        res = analyze_assessment_with_ai(assessment)
        results.append(res)
        rec = res["recommendation"]
        if rec in counts:
            counts[rec] += 1
        counts["total_analyzed"] += 1

    return {
        "counts": counts,
        "results": results,
    }
