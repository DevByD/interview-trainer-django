"""Authentication-related profile models.

Both profiles extend Django's built-in ``User`` via a OneToOneField.
Passwords are managed by Django (PBKDF2 hashing) — never stored or handled
manually anywhere in this project.
"""

from django.contrib.auth.models import User
from django.db import models


class CandidateProfile(models.Model):
    """Extended information for a candidate account."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    phone = models.CharField(max_length=15, blank=True)
    education = models.CharField(max_length=200, blank=True)
    skills = models.TextField(blank=True, help_text="Comma separated list of skills.")
    experience = models.PositiveSmallIntegerField(
        default=0,
        help_text="Total years of professional experience.",
    )
    resume = models.FileField(upload_to="resumes/", blank=True, null=True)
    profile_completed = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["profile_completed"]),
            models.Index(fields=["email_verified"]),
        ]

    def __str__(self) -> str:
        return f"Candidate: {self.user.get_full_name() or self.user.username}"

    @property
    def completion_percentage(self) -> int:
        """Calculate profile completion percentage based on filled profile fields."""
        fields = [
            bool(self.user.first_name.strip() if self.user and self.user.first_name else False),
            bool(self.phone and self.phone.strip()),
            bool(self.education and self.education.strip()),
            bool(self.skills and self.skills.strip()),
            bool(self.experience is not None and self.experience >= 0),
            bool(self.resume),
        ]
        completed = sum(1 for f in fields if f)
        return int((completed / len(fields)) * 100)

    def save(self, *args, **kwargs):
        # A profile counts as complete once the key recruiter-facing fields
        # are filled in. Kept in sync automatically on every save.
        self.profile_completed = bool(
            self.phone and self.phone.strip()
            and self.education and self.education.strip()
            and self.skills and self.skills.strip()
        )
        super().save(*args, **kwargs)


class EmployerProfile(models.Model):
    """Extended information for an employer/recruiter account."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employer_profile",
    )
    company = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Employer: {self.user.get_full_name() or self.user.username} ({self.company})"
