"""Forms for creating and configuring assessments."""

from datetime import datetime, time
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import CandidateProfile
from assessments.coding_bank import ensure_coding_bank_seeded
from assessments.models import CodingQuestion, Question
from assessments.question_bank import ensure_question_bank_seeded


class AssessmentCreateForm(forms.Form):

    candidate = forms.ModelChoiceField(
        queryset=User.objects.filter(candidate_profile__isnull=False).select_related("candidate_profile"),
        label="Select Candidate",
        empty_label="-- Select a registered candidate --",
        widget=forms.Select(attrs={"class": "form-input candidate-select"}),
    )
    title = forms.CharField(
        max_length=200,
        label="Assessment Title",
        initial="Technical & Aptitude Assessment",
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Senior Python Developer Assessment"}),
    )
    SECTION_CHOICES = [
        ("LOGICAL", "Logical Reasoning"),
        ("QUANTITATIVE", "Quantitative Aptitude"),
        ("TECHNICAL", "Technical Aptitude"),
    ]
    sections = forms.MultipleChoiceField(
        choices=SECTION_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "section-checkbox"}),
        initial=["LOGICAL", "QUANTITATIVE", "TECHNICAL"],
        label="Assessment Sections",
        required=True,
    )
    logical_count = forms.IntegerField(
        label="Logical Questions",
        initial=5,
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-input section-count-input", "min": "0"}),
    )
    quant_count = forms.IntegerField(
        label="Quantitative Questions",
        initial=5,
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-input section-count-input", "min": "0"}),
    )
    technical_count = forms.IntegerField(
        label="Technical Questions",
        initial=5,
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-input section-count-input", "min": "0"}),
    )
    include_coding = forms.BooleanField(
        label="Include Coding Assessment",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "coding-toggle-checkbox", "id": "id_include_coding"}),
    )
    coding_count = forms.IntegerField(
        label="Coding Questions",
        initial=2,
        min_value=1,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-input", "min": "1", "max": "10", "id": "id_coding_count"}),
    )
    start_date = forms.DateField(
        label="Start Date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}),
    )
    start_time = forms.TimeField(
        label="Start Time",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
    )
    expire_date = forms.DateField(
        label="Expiry Date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}),
    )
    expire_time = forms.TimeField(
        label="Expiry Time",
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
    )
    duration_minutes = forms.IntegerField(
        label="Duration (minutes)",
        initial=60,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
    )

    def __init__(self, *args, initial_candidate=None, **kwargs):
        ensure_question_bank_seeded()
        ensure_coding_bank_seeded()
        super().__init__(*args, **kwargs)
        now = timezone.localtime(timezone.now())


        if not self.is_bound:
            self.fields["start_date"].initial = now.date()
            self.fields["start_time"].initial = now.strftime("%H:%M")
            # Default expiry 24 hours later
            tomorrow = now + timezone.timedelta(days=1)
            self.fields["expire_date"].initial = tomorrow.date()
            self.fields["expire_time"].initial = tomorrow.strftime("%H:%M")

        if initial_candidate:
            self.fields["candidate"].initial = initial_candidate

    def clean(self):
        cleaned_data = super().clean()
        candidate = cleaned_data.get("candidate")
        sections = cleaned_data.get("sections") or []
        logical_count = cleaned_data.get("logical_count") or 0
        quant_count = cleaned_data.get("quant_count") or 0
        technical_count = cleaned_data.get("technical_count") or 0
        start_date = cleaned_data.get("start_date")
        start_time = cleaned_data.get("start_time")
        expire_date = cleaned_data.get("expire_date")
        expire_time = cleaned_data.get("expire_time")
        duration_minutes = cleaned_data.get("duration_minutes")

        # 1. Candidate validation
        if candidate and not hasattr(candidate, "candidate_profile"):
            self.add_error("candidate", "Selected user is not registered as a candidate.")

        # 2. Sections and question counts validation
        if not sections:
            self.add_error("sections", "Please select at least one assessment section.")

        section_count_map = {
            "LOGICAL": (logical_count, "Logical Reasoning", "logical_count"),
            "QUANTITATIVE": (quant_count, "Quantitative Aptitude", "quant_count"),
            "TECHNICAL": (technical_count, "Technical Aptitude", "technical_count"),
        }

        total_selected_questions = 0
        for sec_key in sections:
            count, sec_name, field_name = section_count_map[sec_key]
            if count <= 0:
                self.add_error(
                    field_name,
                    f"Please specify at least 1 question for the selected '{sec_name}' section.",
                )
            else:
                available_count = Question.objects.filter(section=sec_key).count()
                if count > available_count:
                    self.add_error(
                        field_name,
                        f"Requested {count} questions for {sec_name}, but only {available_count} questions exist in the question bank.",
                    )
                else:
                    total_selected_questions += count


        include_coding = cleaned_data.get("include_coding", False)
        coding_count = cleaned_data.get("coding_count") or 0

        if include_coding:
            if coding_count <= 0:
                self.add_error("coding_count", "Please specify at least 1 coding question when Coding Assessment is enabled.")
            else:
                coding_available = CodingQuestion.objects.count()
                if coding_count > coding_available:
                    self.add_error(
                        "coding_count",
                        f"Requested {coding_count} coding questions, but only {coding_available} questions exist in the coding question bank.",
                    )

        if sections and total_selected_questions <= 0 and not self.errors:
            raise ValidationError("Assessment must have at least one question assigned.")


        # 3. Schedule & Datetime validation
        if start_date and start_time and expire_date and expire_time:
            current_tz = timezone.get_current_timezone()
            naive_start = datetime.combine(start_date, start_time)
            naive_expire = datetime.combine(expire_date, expire_time)

            start_dt = timezone.make_aware(naive_start, current_tz)
            expire_dt = timezone.make_aware(naive_expire, current_tz)

            if expire_dt <= start_dt:
                self.add_error("expire_date", "Expiry date & time must be strictly after the start date & time.")

            cleaned_data["start_datetime"] = start_dt
            cleaned_data["expire_datetime"] = expire_dt

        # 4. Duration validation
        if duration_minutes is not None and duration_minutes <= 0:
            self.add_error("duration_minutes", "Duration must be greater than zero minutes.")

        return cleaned_data