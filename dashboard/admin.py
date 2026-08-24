"""Django admin registration for dashboard models."""

from django.contrib import admin
from .models import AdminActivityLog


@admin.register(AdminActivityLog)
class AdminActivityLogAdmin(admin.ModelAdmin):
    list_display = ("admin_user", "action_type", "details_snippet", "ip_address", "created_at")
    list_filter = ("action_type", "created_at")
    search_fields = ("admin_user__username", "admin_user__email", "details", "ip_address")
    ordering = ("-created_at",)
    readonly_fields = ("admin_user", "action_type", "details", "ip_address", "created_at")

    @admin.display(description="Details")
    def details_snippet(self, obj):
        if len(obj.details) > 60:
            return f"{obj.details[:57]}..."
        return obj.details
