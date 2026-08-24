from django.contrib import admin
from .models import (
    Answer,
    Assessment,
    AssessmentCodingQuestion,
    AssessmentGroup,
    AssessmentQuestion,
    CodingQuestion,
    CodingSubmission,
    CodingTestCase,
    Question,
)


class AssessmentInline(admin.TabularInline):
    model = Assessment
    extra = 0
    fields = ("candidate", "status", "candidate_status", "violation_count", "token")
    readonly_fields = ("token",)
    show_change_link = True
    can_delete = False


@admin.register(AssessmentGroup)
class AssessmentGroupAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "employer",
        "start_time",
        "expire_time",
        "duration_minutes",
        "has_coding",
        "created_at",
    )
    search_fields = ("title", "employer__username", "employer__email")
    list_filter = ("has_coding", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [AssessmentInline]


class AssessmentQuestionInline(admin.TabularInline):
    model = AssessmentQuestion
    extra = 0
    autocomplete_fields = ("question",)
    ordering = ("order", "id")


class AssessmentCodingQuestionInline(admin.TabularInline):
    model = AssessmentCodingQuestion
    extra = 0
    autocomplete_fields = ("question",)
    ordering = ("order", "id")


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ("question", "selected_answer", "is_correct")
    can_delete = False


class CodingSubmissionInline(admin.TabularInline):
    model = CodingSubmission
    extra = 0
    readonly_fields = ("question", "language", "passed_test_cases", "total_test_cases", "score", "is_submitted", "last_saved_at")
    can_delete = False


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "employer",
        "candidate",
        "has_coding",
        "status",
        "candidate_status",
        "violation_count",
        "malpractice_status",
        "start_time",
        "expire_time",
        "duration_minutes",
    )
    search_fields = ("title", "token", "employer__username", "candidate__username")
    list_filter = ("has_coding", "status", "candidate_status", "malpractice_status", "duration_minutes")
    ordering = ("-created_at",)
    readonly_fields = ("token", "violation_count", "last_violation_type", "last_violation_at", "auto_submitted_for_malpractice", "created_at", "updated_at")

    autocomplete_fields = ("employer", "candidate")
    inlines = [AssessmentQuestionInline, AssessmentCodingQuestionInline, AnswerInline, CodingSubmissionInline]



@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "short_question_text",
        "section",
        "category",
        "difficulty",
        "correct_answer",
        "source_type",
        "is_active",
        "is_reviewed",
        "is_approved",
        "usage_count_display",
        "created_at",
    )
    search_fields = (
        "question_text",
        "category",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "ai_provider",
    )
    list_filter = (
        "section",
        "difficulty",
        "source_type",
        "is_active",
        "is_reviewed",
        "is_approved",
    )
    ordering = ("section", "id")
    actions = ["make_active", "make_inactive", "approve_questions"]

    @admin.display(description="Question Text")
    def short_question_text(self, obj):
        if len(obj.question_text) > 80:
            return f"{obj.question_text[:77]}..."
        return obj.question_text

    @admin.display(description="Usage Count")
    def usage_count_display(self, obj):
        return obj.usage_count

    @admin.action(description="Activate selected questions")
    def make_active(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} question(s) successfully activated.")

    @admin.action(description="Deactivate selected questions (safe soft-deactivation)")
    def make_inactive(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} question(s) successfully deactivated.")

    @admin.action(description="Mark selected questions as Reviewed & Approved")
    def approve_questions(self, request, queryset):
        count = queryset.update(is_reviewed=True, is_approved=True)
        self.message_user(request, f"{count} question(s) marked as reviewed & approved.")


@admin.register(AssessmentQuestion)
class AssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ("assessment", "question", "order", "question_section")
    search_fields = ("assessment__title", "question__question_text")
    list_filter = ("question__section", "question__difficulty")
    ordering = ("assessment", "order", "id")

    @admin.display(description="Section")
    def question_section(self, obj):
        return obj.question.get_section_display()


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = (
        "assessment",
        "question",
        "selected_answer",
        "is_correct",
    )
    search_fields = ("assessment__title", "question__question_text")
    list_filter = ("is_correct", "question__section")


class CodingTestCaseInline(admin.TabularInline):
    model = CodingTestCase
    extra = 1
    ordering = ("order", "id")


@admin.register(CodingQuestion)
class CodingQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "slug",
        "category",
        "difficulty",
        "source_type",
        "time_limit_seconds",
        "memory_limit_mb",
        "is_active",
        "is_reviewed",
        "is_approved",
        "usage_count_display",
        "max_score",
        "created_at",
    )
    search_fields = ("title", "slug", "description", "category", "ai_provider")
    list_filter = ("category", "difficulty", "source_type", "is_active", "is_reviewed", "is_approved")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CodingTestCaseInline]
    actions = ["make_active", "make_inactive", "approve_questions"]

    @admin.display(description="Usage Count")
    def usage_count_display(self, obj):
        return obj.usage_count

    @admin.action(description="Activate selected coding challenges")
    def make_active(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} coding challenge(s) successfully activated.")

    @admin.action(description="Deactivate selected coding challenges (safe soft-deactivation)")
    def make_inactive(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} coding challenge(s) successfully deactivated.")

    @admin.action(description="Mark selected coding challenges as Reviewed & Approved")
    def approve_questions(self, request, queryset):
        count = queryset.update(is_reviewed=True, is_approved=True)
        self.message_user(request, f"{count} coding challenge(s) marked as reviewed & approved.")



@admin.register(CodingTestCase)
class CodingTestCaseAdmin(admin.ModelAdmin):
    list_display = ("question", "order", "is_sample", "short_input", "short_output")
    list_filter = ("is_sample", "question")
    search_fields = ("question__title", "input_data", "expected_output")

    @admin.display(description="Input")
    def short_input(self, obj):
        return (obj.input_data[:40] + "...") if len(obj.input_data) > 40 else obj.input_data

    @admin.display(description="Expected Output")
    def short_output(self, obj):
        return (obj.expected_output[:40] + "...") if len(obj.expected_output) > 40 else obj.expected_output


@admin.register(AssessmentCodingQuestion)
class AssessmentCodingQuestionAdmin(admin.ModelAdmin):
    list_display = ("assessment", "question", "order")
    search_fields = ("assessment__title", "question__title")
    ordering = ("assessment", "order", "id")


@admin.register(CodingSubmission)
class CodingSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "assessment",
        "question",
        "language",
        "passed_test_cases",
        "total_test_cases",
        "score",
        "is_submitted",
        "last_saved_at",
    )
    list_filter = ("language", "is_submitted")
    search_fields = ("assessment__title", "question__title")