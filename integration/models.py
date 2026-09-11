"""Integration app models.

Maintains audit trails and synchronization tracking between HumanDB ATS and Interview Trainer.
"""

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class IntegrationSyncLog(models.Model):
    """Audit log of HumanDB <-> Interview integration API events."""

    class ActionType(models.TextChoices):
        CANDIDATE_SYNC = "CANDIDATE_SYNC", "Candidate Sync"
        ASSESSMENT_CREATE = "ASSESSMENT_CREATE", "Assessment Create"
        RESULT_CALLBACK = "RESULT_CALLBACK", "Result Callback"

    action = models.CharField(
        max_length=50,
        choices=ActionType.choices,
        db_index=True,
    )
    human_db_user_id = models.UUIDField(null=True, blank=True, db_index=True)
    assessment_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    response_status = models.PositiveIntegerField(default=200)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["human_db_user_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.action}] HumanDB:{self.human_db_user_id} @ {self.created_at}"
