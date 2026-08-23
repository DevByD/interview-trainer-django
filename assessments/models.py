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
    has_coding = models.BooleanField(default=False)
    violation_count = models.PositiveIntegerField(
        default=0,
        help_text="Count of proctoring violations recorded during the assessment",
    )
    max_violations = models.PositiveIntegerField(
        default=3,
        help_text="Maximum allowed violations before automatic submission",
    )
    malpractice_status = models.BooleanField(
        default=False,
        help_text="Flag indicating if the candidate exceeded the maximum allowed violations",
    )
    last_violation_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Type of the last recorded violation (e.g. FULLSCREEN_EXIT, DEVTOOLS_SHORTCUT, TAB_SWITCH)",
    )
    last_violation_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the most recent violation",
    )
    auto_submitted_for_malpractice = models.BooleanField(
        default=False,
        help_text="Flag indicating if the assessment was terminated and auto-submitted for malpractice",
    )
    submission_reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Reason for assessment submission (e.g. standard completion, auto-submitted for malpractice)",
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

    @property
    def deadline(self):
        """Authoritative server-side deadline for the assessment."""
        from datetime import timedelta
        return min(self.start_time + timedelta(minutes=self.duration_minutes), self.expire_time)

    @property
    def is_missed(self) -> bool:
        return (
            self.status == self.Status.EXPIRED
            or self.candidate_status == self.CandidateStatus.NOT_ATTENDED
        )

    @property
    def questions_count(self) -> int:
        return self.questions.count()

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets

            self.token = secrets.token_urlsafe(32)
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


class CodingQuestion(models.Model):
    """A coding challenge / programming problem."""

    class Categories(models.TextChoices):
        ARRAYS = "arrays", "Arrays"
        STRINGS = "strings", "Strings"
        HASHING = "hashing", "Hashing"
        TWO_POINTERS = "two_pointers", "Two Pointers / Sliding Window"
        SEARCH_SORT = "search_sort", "Searching / Sorting"
        STACK_QUEUE = "stack_queue", "Stack / Queue"
        LINKED_LIST = "linked_list", "Linked List"
        RECURSION = "recursion", "Recursion"
        TREES = "trees", "Trees"
        DP = "dp", "Dynamic Programming"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    category = models.CharField(
        max_length=30,
        choices=Categories.choices,
        default=Categories.ARRAYS,
        help_text="Primary algorithmic domain or data structure category",
    )
    description = models.TextField(help_text="Detailed problem statement")
    input_format = models.TextField(help_text="Expected input format")
    output_format = models.TextField(help_text="Expected output format")
    constraints = models.TextField(blank=True, default="", help_text="Input size & performance constraints")
    sample_input = models.TextField(help_text="Sample input for display")
    sample_output = models.TextField(help_text="Sample expected output for display")
    explanation = models.TextField(blank=True, default="", help_text="Explanation of the sample test cases")
    difficulty = models.CharField(
        max_length=10,
        choices=Question.Difficulties.choices,
        default=Question.Difficulties.MEDIUM,
    )

    starter_code = models.JSONField(
        default=dict,
        help_text="Dictionary of starter scaffold comments by language: {'python': '...', 'java': '...', 'cpp': '...', 'javascript': '...'}",
    )
    max_score = models.PositiveIntegerField(default=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"[{self.get_difficulty_display()}] {self.title}"


class CodingTestCase(models.Model):
    """Test cases for evaluating a CodingQuestion. Separated into visible sample vs hidden evaluation cases."""

    question = models.ForeignKey(
        CodingQuestion,
        on_delete=models.CASCADE,
        related_name="test_cases",
    )
    input_data = models.TextField()
    expected_output = models.TextField()
    is_sample = models.BooleanField(
        default=False,
        help_text="True if this is a sample visible test case; False if hidden evaluator test case.",
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        tag = "Sample" if self.is_sample else "Hidden"
        return f"{self.question.title} - Test Case #{self.order} ({tag})"


class AssessmentCodingQuestion(models.Model):
    """Join model: which coding questions are assigned to which assessment."""

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="coding_questions",
    )
    question = models.ForeignKey(
        CodingQuestion,
        on_delete=models.CASCADE,
        related_name="assessment_assignments",
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "question"],
                name="unique_coding_question_per_assessment",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assessment.title}: Coding Q{self.question_id}"


class CodingSubmission(models.Model):
    """Candidate's saved or submitted code for a single coding problem in an assessment."""

    class Language(models.TextChoices):
        PYTHON = "python", "Python 3"
        JAVA = "java", "Java"
        CPP = "cpp", "C++"
        JAVASCRIPT = "javascript", "JavaScript"

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="coding_submissions",
    )
    question = models.ForeignKey(
        CodingQuestion,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    language = models.CharField(
        max_length=20,
        choices=Language.choices,
        default=Language.PYTHON,
    )
    source_code = models.TextField(blank=True, default="")
    passed_test_cases = models.PositiveIntegerField(default=0)
    total_test_cases = models.PositiveIntegerField(default=0)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_submitted = models.BooleanField(default=False)
    last_saved_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "question"],
                name="unique_submission_per_assessment_coding_question",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assessment.title} - {self.question.title} ({self.language}): {self.passed_test_cases}/{self.total_test_cases}"