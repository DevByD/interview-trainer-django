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

    context = {
        "result": result,
        "assessment": result.assessment,
        "logical_pct": logical_pct,
        "quant_pct": quant_pct,
        "tech_pct": tech_pct,
        "chart_data_json": json.dumps(chart_data),
    }
    return render(request, "results/candidate_result.html", context)


@employer_required
def employer_result(request, result_id):
    """Employer view for candidate assessment result."""
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

    context = {
        "result": result,
        "assessment": result.assessment,
        "candidate": result.assessment.candidate,
        "candidate_profile": getattr(result.assessment.candidate, "candidate_profile", None),
        "logical_pct": logical_pct,
        "quant_pct": quant_pct,
        "tech_pct": tech_pct,
        "chart_data_json": json.dumps(chart_data),
    }
    return render(request, "results/employer_result.html", context)
