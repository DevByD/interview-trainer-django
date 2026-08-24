"""Models for platform dashboard telemetry and administrative audit activity logging."""

from django.conf import settings
from django.db import models


class AdminActivityLog(models.Model):
    """Audit log capturing security-relevant administrative actions without storing secrets."""

    class ActionTypes(models.TextChoices):
        ADMIN_LOGIN = "ADMIN_LOGIN", "Admin Login"
        QUESTION_CREATED = "QUESTION_CREATED", "Question Created"
        QUESTION_UPDATED = "QUESTION_UPDATED", "Question Updated"
        QUESTION_STATUS_TOGGLED = "QUESTION_STATUS_TOGGLED", "Question Status Toggled"
        QUESTION_DELETED = "QUESTION_DELETED", "Question Deleted"
        BULK_QUESTION_ACTION = "BULK_QUESTION_ACTION", "Bulk Question Action"
        EMPLOYER_STATUS_CHANGED = "EMPLOYER_STATUS_CHANGED", "Employer Status Changed"
        CANDIDATE_VIEWED = "CANDIDATE_VIEWED", "Candidate Viewed"
        ASSESSMENT_VIEWED = "ASSESSMENT_VIEWED", "Assessment Viewed"
        REPORT_GENERATED = "REPORT_GENERATED", "Report Generated"

    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_activity_logs",
    )
    action_type = models.CharField(
        max_length=50,
        choices=ActionTypes.choices,
        db_index=True,
    )
    details = models.TextField(blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action_type", "created_at"]),
        ]

    def __str__(self) -> str:
        user_name = self.admin_user.username if self.admin_user else "System"
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {user_name} - {self.get_action_type_display()}"


def log_admin_activity(admin_user, action_type, details="", request=None):
    """Convenience helper to record administrative actions safely."""
    ip = None
    if request:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
    return AdminActivityLog.objects.create(
        admin_user=admin_user if admin_user and admin_user.is_authenticated else None,
        action_type=action_type,
        details=details,
        ip_address=ip,
    )
