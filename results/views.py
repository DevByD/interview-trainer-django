"""Views for candidate and employer assessment result reports."""

import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from accounts.decorators import candidate_required, employer_required
from assessments.models import Assessment
from results.models import Result


@candidate_required
def candidate_result(request, result_id):
    """Candidate view for their own assessment result with Chart.js visualization."""
    result = get_object_or_404(
        Result.objects.select_related(
            "assessment",
            "assessment__employer",
            "assessment__employer__employer_profile",
            "assessment__candidate",
        ),
        pk=result_id,
    )

    if result.assessment.candidate != request.user:
        raise PermissionDenied("You do not have permission to view this assessment result.")

    # Section percentage calculations for cards & chart
    logical_pct = round((result.logical_correct / result.logical_total * 100), 1) if result.logical_total else 0
    quant_pct = round((result.quant_correct / result.quant_total * 100), 1) if result.quant_total else 0
    tech_pct = round((result.technical_correct / result.technical_total * 100), 1) if result.technical_total else 0

    chart_data = {
        "labels": ["Logical Reasoning", "Quantitative Aptitude", "Technical Aptitude"],
        "correct": [result.logical_correct, result.quant_correct, result.technical_correct],
        "incorrect": [
            result.logical_total - result.logical_correct,
            result.quant_total - result.quant_correct,
            result.technical_total - result.technical_correct,
        ],
        "totals": [result.logical_total, result.quant_total, result.technical_total],
    }

    coding_submissions = []
    if result.has_coding or result.assessment.has_coding:
        coding_submissions = (
            result.assessment.coding_submissions.select_related("question")
            .order_by("question__id")
        )

    context = {
        "result": result,
        "assessment": result.assessment,
        "has_coding": result.has_coding or result.assessment.has_coding,
        "coding_submissions": coding_submissions,
        "logical_pct": logical_pct,
        "quant_pct": quant_pct,
        "tech_pct": tech_pct,
        "chart_data_json": json.dumps(chart_data),
    }
    return render(request, "results/candidate_result.html", context)


@employer_required
def employer_result(request, result_id):
    """Employer view for candidate assessment result with comprehensive evaluation metrics & charts."""
    result = get_object_or_404(
        Result.objects.select_related(
            "assessment",
            "assessment__candidate",
            "assessment__candidate__candidate_profile",
            "assessment__employer",
        ),
        pk=result_id,
    )

    if result.assessment.employer != request.user:
        raise PermissionDenied("You do not have permission to view results for this assessment.")

    # Time calculations
    time_taken_str = "N/A"
    if result.completed_at and result.assessment.start_time:
        delta = result.completed_at - result.assessment.start_time
        total_seconds = max(0, int(delta.total_seconds()))
        mins = total_seconds // 60
        secs = total_seconds % 60
        time_taken_str = f"{mins}m {secs}s"

    # Section percentage calculations
    logical_pct = round((result.logical_correct / result.logical_total * 100), 1) if result.logical_total else 0
    quant_pct = round((result.quant_correct / result.quant_total * 100), 1) if result.quant_total else 0
    tech_pct = round((result.technical_correct / result.technical_total * 100), 1) if result.technical_total else 0

    has_coding = result.has_coding or result.assessment.has_coding
    coding_submissions = []
    attempted_coding_count = 0
    passed_coding_count = 0
    total_test_cases = 0
    passed_test_cases = 0

    if has_coding:
        coding_submissions = list(
            result.assessment.coding_submissions.select_related("question")
            .order_by("question__id")
        )
        for sub in coding_submissions:
            if sub.source_code and sub.source_code.strip():
                attempted_coding_count += 1
            if sub.total_test_cases > 0 and sub.passed_test_cases == sub.total_test_cases:
                passed_coding_count += 1
            total_test_cases += sub.total_test_cases
            passed_test_cases += sub.passed_test_cases

    chart_data = {
        "labels": ["Logical Reasoning", "Quantitative Aptitude", "Technical Aptitude"],
        "correct": [result.logical_correct, result.quant_correct, result.technical_correct],
        "incorrect": [
            result.logical_total - result.logical_correct,
            result.quant_total - result.quant_correct,
            result.technical_total - result.technical_correct,
        ],
        "totals": [result.logical_total, result.quant_total, result.technical_total],
    }

    comparison_chart_data = {
        "labels": ["Aptitude", "Coding", "Overall Score"] if has_coding else ["Aptitude Score", "Overall Score"],
        "scores": [float(result.aptitude_score), float(result.coding_score), float(result.overall_score)] if has_coding else [float(result.aptitude_score), float(result.overall_score)],
    }

    context = {
        "result": result,
        "assessment": result.assessment,
        "candidate": result.assessment.candidate,
        "candidate_profile": getattr(result.assessment.candidate, "candidate_profile", None),
        "has_coding": has_coding,
        "coding_submissions": coding_submissions,
        "total_coding_count": len(coding_submissions),
        "attempted_coding_count": attempted_coding_count,
        "passed_coding_count": passed_coding_count,
        "total_test_cases": total_test_cases,
        "passed_test_cases": passed_test_cases,
        "time_taken_str": time_taken_str,
        "logical_pct": logical_pct,
        "quant_pct": quant_pct,
        "tech_pct": tech_pct,
        "chart_data_json": json.dumps(chart_data),
        "comparison_chart_json": json.dumps(comparison_chart_data),
    }
    return render(request, "results/employer_result.html", context)


@employer_required
def employer_result_csv_export(request, result_id):
    """Export candidate assessment evaluation report as CSV."""
    import csv
    from django.http import HttpResponse
    from django.utils.text import slugify

    result = get_object_or_404(
        Result.objects.select_related(
            "assessment",
            "assessment__candidate",
            "assessment__employer",
        ),
        pk=result_id,
    )

    if result.assessment.employer != request.user:
        raise PermissionDenied("You do not have permission to export results for this assessment.")

    candidate = result.assessment.candidate
    candidate_name = candidate.get_full_name() or candidate.username

    response = HttpResponse(content_type="text/csv")
    filename = f"result_{slugify(result.assessment.title)}_{slugify(candidate.username)}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Candidate Name",
        "Email",
        "Status",
        "Aptitude Score",
        "Coding Score",
        "Overall Score",
        "Violations",
        "Auto Submitted",
        "Submission Reason",
        "Completed At",
    ])

    writer.writerow([
        candidate_name,
        candidate.email,
        result.assessment.get_status_display(),
        f"{result.aptitude_score}%",
        f"{result.coding_score}%" if (result.has_coding or result.assessment.has_coding) else "N/A",
        f"{result.overall_score}%",
        f"{result.violation_count}/3",
        "Yes" if result.auto_submitted_for_malpractice else "No",
        result.submission_reason or "Standard candidate completion",
        result.completed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if result.completed_at else "N/A",
    ])

    return response


@employer_required
def employer_all_results_csv_export(request):
    """Export all candidate evaluation results for the authenticated employer as CSV."""
    import csv
    from django.http import HttpResponse

    results = (
        Result.objects.filter(assessment__employer=request.user)
        .select_related("assessment", "assessment__candidate")
        .order_by("-completed_at")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="all_assessment_results.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Candidate Name",
        "Email",
        "Assessment Title",
        "Status",
        "Aptitude Score",
        "Coding Score",
        "Overall Score",
        "Violations",
        "Auto Submitted",
        "Submission Reason",
        "Completed At",
    ])

    for res in results:
        cand = res.assessment.candidate
        cand_name = cand.get_full_name() or cand.username
        writer.writerow([
            cand_name,
            cand.email,
            res.assessment.title,
            res.assessment.get_status_display(),
            f"{res.aptitude_score}%",
            f"{res.coding_score}%" if (res.has_coding or res.assessment.has_coding) else "N/A",
            f"{res.overall_score}%",
            f"{res.violation_count}/3",
            "Yes" if res.auto_submitted_for_malpractice else "No",
            res.submission_reason or "Standard candidate completion",
            res.completed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if res.completed_at else "N/A",
        ])

    return response