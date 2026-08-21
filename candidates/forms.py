import os
from django import forms
from django.core.exceptions import ValidationError

from accounts.models import CandidateProfile

MAX_RESUME_SIZE_MB = 5
ALLOWED_RESUME_EXTENSIONS = [".pdf", ".doc", ".docx"]
DISALLOWED_EXTENSIONS = [
    ".exe", ".bat", ".cmd", ".sh", ".php", ".phtml", ".py",
    ".js", ".jar", ".vbs", ".msi", ".dll", ".com", ".scr",
]


class CandidateProfileForm(forms.ModelForm):
    name = forms.CharField(
        max_length=150,
        required=False,
        label="Full Name",
        widget=forms.TextInput(
            attrs={"placeholder": "e.g. John Doe", "class": "form-input"}
        ),
    )

    class Meta:
        model = CandidateProfile
        fields = ["name", "phone", "education", "skills", "experience", "resume"]
        widgets = {
            "phone": forms.TextInput(
                attrs={"placeholder": "+91 98765 43210", "class": "form-input"}
            ),
            "education": forms.TextInput(
                attrs={"placeholder": "e.g. B.Tech Computer Science, XYZ University", "class": "form-input"}
            ),
            "skills": forms.Textarea(
                attrs={"rows": 3, "placeholder": "e.g. Python, SQL, Django, Data Structures, Git", "class": "form-input"}
            ),
            "experience": forms.NumberInput(
                attrs={"min": 0, "max": 50, "class": "form-input"}
            ),
            "resume": forms.FileInput(
                attrs={"class": "form-input file-input", "accept": ".pdf,.doc,.docx"}
            ),
        }
        help_texts = {
            "skills": "Comma separated list of your technical and soft skills.",
            "experience": "Total years of professional experience.",
            "resume": "Allowed formats: PDF, DOC, DOCX. Maximum file size: 5 MB.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields["name"].initial = (
                self.instance.user.get_full_name() or self.instance.user.first_name
            )

    def clean_resume(self):
        resume = self.cleaned_data.get("resume")
        if resume and hasattr(resume, "size"):
            if resume.size > MAX_RESUME_SIZE_MB * 1024 * 1024:
                raise ValidationError(f"Resume file size cannot exceed {MAX_RESUME_SIZE_MB}MB.")

            filename = resume.name.lower()
            ext = os.path.splitext(filename)[1]

            # Reject dangerous / executable extensions
            if ext in DISALLOWED_EXTENSIONS:
                raise ValidationError("Executable and script files are strictly prohibited.")

            if ext not in ALLOWED_RESUME_EXTENSIONS:
                raise ValidationError(
                    "Invalid file type. Only PDF, DOC, and DOCX documents are allowed."
                )

            # Validate MIME / content type if available
            content_type = getattr(resume, "content_type", "")
            if content_type:
                allowed_mimes = [
                    "application/pdf",
                    "application/msword",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/octet-stream",
                ]
                if content_type not in allowed_mimes and not ext in ALLOWED_RESUME_EXTENSIONS:
                    raise ValidationError("Uploaded file content is not a valid document.")

        return resume

    def save(self, commit: bool = True):
        profile = super().save(commit=False)
        name = self.cleaned_data.get("name", "").strip()
        if name and profile.user:
            parts = name.split(None, 1)
            profile.user.first_name = parts[0]
            profile.user.last_name = parts[1] if len(parts) > 1 else ""
            profile.user.save(update_fields=["first_name", "last_name"])
        if commit:
            profile.save()
        return profile
