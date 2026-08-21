from django.contrib import admin

from .models import Answer, Assessment, AssessmentQuestion, Question


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "employer",
        "candidate",
        "status",
        "candidate_status",
        "start_time",
        "expire_time",
        "duration_minutes",
    )
    search_fields = ("title", "token", "employer__username", "candidate__username")
    list_filter = ("status", "candidate_status", "duration_minutes")
    ordering = ("-created_at",)
    readonly_fields = ("token", "created_at", "updated_at")
    autocomplete_fields = ("employer", "candidate")


class AssessmentQuestionInline(admin.TabularInline):
    model = AssessmentQuestion
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "short_question_text",
        "section",
        "difficulty",
        "correct_answer",
        "created_at",
    )
    search_fields = ("question_text",)
    list_filter = ("section", "difficulty")
    ordering = ("section", "id")

    @admin.display(description="Question")
    def short_question_text(self, obj):
        return obj.question_text[:80]


@admin.register(AssessmentQuestion)
class AssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ("assessment", "question", "order", "question_section")
    search_fields = ("assessment__title", "question__question_text")
    list_filter = ("question__section",)
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
