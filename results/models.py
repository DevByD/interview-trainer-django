"""Result model — automated grading output for a completed assessment.

Populated in Phase 3; defined now so migrations/admin are ready.
"""

from django.db import models

from assessments.models import Assessment


class Result(models.Model):
    assessment = models.OneToOneField(
        Assessment,
        on_delete=models.CASCADE,
        related_name="result",
    )
    logical_correct = models.PositiveIntegerField(default=0)
    logical_total = models.PositiveIntegerField(default=0)
    quant_correct = models.PositiveIntegerField(default=0)
    quant_total = models.PositiveIntegerField(default=0)
    technical_correct = models.PositiveIntegerField(default=0)
    technical_total = models.PositiveIntegerField(default=0)
    total_correct = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    has_coding = models.BooleanField(default=False)
    aptitude_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    coding_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    violation_count = models.PositiveIntegerField(default=0)
    auto_submitted_for_malpractice = models.BooleanField(default=False)
    submission_reason = models.CharField(max_length=255, blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)



    class Meta:
        ordering = ["-completed_at"]

    def __str__(self) -> str:
        if self.has_coding:
            return f"Result for {self.assessment.title}: Overall {self.overall_score}% (Aptitude: {self.aptitude_score}%, Coding: {self.coding_score}%)"
        return f"Result for {self.assessment.title}: {self.percentage}%"

    @property
    def passed(self) -> bool:
        if self.has_coding:
            return self.overall_score >= 50
        return self.percentage >= 50