"""Core assessment domain models.

Assessment lifecycle (Phase 2+ will drive transitions):

    PENDING   -> assessment scheduled, not yet started
    ONGOING   -> candidate has started the test
    COMPLETED -> candidate submitted the test
    EXPIRED   -> expire_time passed without completion

Candidate attendance:

    NOT_STARTED   -> candidate never opened the test
    ATTENDED      -> candidate attended/submitted
    NOT_ATTENDED  -> assessment expired without attendance ("missed test")
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Question(models.Model):
    """A multiple-choice question bank entry."""

    class Sections(models.TextChoices):
        LOGICAL = "LOGICAL", "Logical Reasoning"
        QUANTITATIVE = "QUANTITATIVE", "Quantitative Aptitude"
        TECHNICAL = "TECHNICAL", "Technical Aptitude"

    class Difficulties(models.TextChoices):
        EASY = "EASY", "Easy"
        MEDIUM = "MEDIUM", "Medium"
        HARD = "HARD", "Hard"

    section = models.CharField(
        max_length=20,
        choices=Sections.choices,
        db_index=True,
    )
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_answer = models.CharField(
        max_length=1,
        choices=[("A", "Option A"), ("B", "Option B"), ("C", "Option C"), ("D", "Option D")],
    )
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulties.choices,
        default=Difficulties.EASY,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["section", "id"]
        indexes = [
            models.Index(fields=["section", "difficulty"]),
        ]

    def __str__(self) -> str:
        return f"[{self.get_section_display()}] {self.question_text[:60]}"

    @property
    def options(self) -> dict:
        return {
            "A": self.option_a,
            "B": self.option_b,
            "C": self.option_c,
            "D": self.option_d,
        }


class Assessment(models.Model):
    """An assessment assigned by an employer to a single candidate."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ONGOING = "ONGOING", "Ongoing"
        COMPLETED = "COMPLETED", "Completed"
        EXPIRED = "EXPIRED", "Expired"

    class CandidateStatus(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not Started"
        ATTENDED = "ATTENDED", "Attended"
        NOT_ATTENDED = "NOT_ATTENDED", "Not Attended"

    employer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessments_created",
    )
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessments_assigned",
    )
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    expire_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    token = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    candidate_status = models.CharField(
        max_length=15,
        choices=CandidateStatus.choices,
        default=CandidateStatus.NOT_STARTED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "candidate_status"]),
            models.Index(fields=["expire_time"]),
            models.Index(fields=["employer", "candidate"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(expire_time__gt=F("start_time")),
                name="assessment_expire_after_start",
            ),
            models.CheckConstraint(
                condition=Q(duration_minutes__gt=0),
                name="assessment_duration_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.candidate.username} <- {self.employer.username})"

    def save(self, *args, **kwargs):
        if not self.token:
            from uuid import uuid4

            self.token = uuid4().hex
        super().save(*args, **kwargs)


class AssessmentQuestion(models.Model):
    """Join model: which questions belong to which assessment."""

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="assessment_questions",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "question"],
                name="unique_question_per_assessment",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assessment.title}: Q{self.question_id}"


class Answer(models.Model):
    """A candidate's selected answer for one question of one assessment."""

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    selected_answer = models.CharField(max_length=1)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "question"],
                name="unique_answer_per_assessment_question",
            ),
            models.CheckConstraint(
                condition=Q(selected_answer__in=("A", "B", "C", "D")),
                name="answer_is_valid_option",
            ),
        ]
        indexes = [
            models.Index(fields=["is_correct"]),
        ]

    def __str__(self) -> str:
        return f"{self.assessment_id}/{self.question_id} -> {self.selected_answer}"
