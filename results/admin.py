from django.contrib import admin

from .models import Result


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = (
        "assessment",
        "total_correct",
        "total_questions",
        "percentage",
        "completed_at",
    )
    search_fields = ("assessment__title", "assessment__candidate__username")
    list_filter = ("assessment__status",)
    ordering = ("-completed_at",)
    readonly_fields = (
        "logical_correct",
        "logical_total",
        "quant_correct",
        "quant_total",
        "technical_correct",
        "technical_total",
        "total_correct",
        "total_questions",
        "percentage",
    )
