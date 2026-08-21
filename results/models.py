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
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-completed_at"]

    def __str__(self) -> str:
        return f"Result for {self.assessment.title}: {self.percentage}%"

    @property
    def passed(self) -> bool:
        return self.percentage >= 50
