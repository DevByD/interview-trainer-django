"""Forms for creating and configuring assessments with single and bulk candidate assignment."""

import json
from datetime import datetime, time
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import CandidateProfile
from assessments.coding_bank import ensure_coding_bank_seeded
from assessments.document_parser import (
    process_uploaded_document,
    parse_questions_from_text,
    validate_document_file,
)
from assessments.models import AssessmentDocument, CodingQuestion, Question
from assessments.question_bank import ensure_question_bank_seeded


class AssessmentCreateForm(forms.Form):
    """Form to create and schedule assessments with support for single/bulk candidate assignment and document upload."""

    # Question Source Selection
    QUESTION_SOURCE_CHOICES = [
        ("BANK", "Select Existing Questions"),
        ("DOCUMENT", "Upload Question Document"),
    ]
    question_source = forms.ChoiceField(
        choices=QUESTION_SOURCE_CHOICES,
        initial="BANK",
        widget=forms.RadioSelect(attrs={"class": "question-source-radio"}),
        label="Question Source",
        required=False,
    )

    # Document Upload Fields
    document_file = forms.FileField(
        label="Upload Question Document",
        required=False,
        widget=forms.FileInput(attrs={"accept": ".pdf,.docx,.txt", "class": "form-input-file", "id": "id_document_file"}),
    )
    document_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_document_id"}),
    )
    document_question_count = forms.IntegerField(
        label="Number of Questions for Candidates",
        min_value=1,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-input", "min": "1", "id": "id_document_question_count"}),
    )
    document_questions_payload = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "id_document_questions_payload"}),
    )

    # Bulk candidate selection (Multiple Candidates)
    candidates = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(candidate_profile__isnull=False).select_related("candidate_profile"),
        label="Select Candidates",
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "candidate-checkbox"}),
    )

    # Legacy single candidate selection (Preserved for backwards-compatibility)
    candidate = forms.ModelChoiceField(
        queryset=User.objects.filter(candidate_profile__isnull=False).select_related("candidate_profile"),
        label="Select Candidate (Single)",
        empty_label="-- Select a registered candidate --",
        required=False,
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
        required=False,
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

    def __init__(self, *args, initial_candidate=None, initial_candidates=None, employer=None, **kwargs):
        ensure_question_bank_seeded()
        ensure_coding_bank_seeded()
        super().__init__(*args, **kwargs)
        self.employer = employer
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
            self.fields["candidates"].initial = [initial_candidate]
        elif initial_candidates:
            self.fields["candidates"].initial = initial_candidates

    def clean(self):
        cleaned_data = super().clean()
        candidates = cleaned_data.get("candidates")
        candidate = cleaned_data.get("candidate")
        question_source = cleaned_data.get("question_source") or "BANK"
        sections = cleaned_data.get("sections") or []
        logical_count = cleaned_data.get("logical_count") or 0
        quant_count = cleaned_data.get("quant_count") or 0
        technical_count = cleaned_data.get("technical_count") or 0
        start_date = cleaned_data.get("start_date")
        start_time = cleaned_data.get("start_time")
        expire_date = cleaned_data.get("expire_date")
        expire_time = cleaned_data.get("expire_time")
        duration_minutes = cleaned_data.get("duration_minutes")

        cleaned_data["question_source"] = question_source

        # 1. Candidate Selection Resolution (Support both bulk list and single select)
        selected_candidates_list = []
        if candidates and len(candidates) > 0:
            selected_candidates_list = list(candidates)
        elif candidate:
            selected_candidates_list = [candidate]

        if not selected_candidates_list:
            self.add_error("candidates", "Please select at least one candidate for this assessment.")
        else:
            # Validate candidate profile existence
            for cand in selected_candidates_list:
                if not hasattr(cand, "candidate_profile"):
                    self.add_error("candidates", f"User '{cand.username}' does not have a candidate profile.")

        cleaned_data["selected_candidates"] = selected_candidates_list

        # 2. Question Source Handling
        if question_source == "DOCUMENT":
            document_id = cleaned_data.get("document_id")
            doc_file = cleaned_data.get("document_file")
            payload_str = cleaned_data.get("document_questions_payload", "")
            doc_instance = None

            if document_id:
                try:
                    doc_instance = AssessmentDocument.objects.get(pk=document_id)
                except AssessmentDocument.DoesNotExist:
                    self.add_error("document_file", "The specified document could not be found.")
            elif doc_file:
                is_valid, err, ext, size = validate_document_file(doc_file)
                if not is_valid:
                    self.add_error("document_file", err)
                else:
                    employer_user = getattr(self, "employer", None)
                    doc_instance = AssessmentDocument.objects.create(
                        employer=employer_user,
                        file=doc_file,
                        original_filename=doc_file.name,
                        file_type=ext,
                        file_size=size,
                        status=AssessmentDocument.Status.PENDING,
                    )
                    success, parse_err, parsed_qs = process_uploaded_document(doc_instance)
                    if not success:
                        self.add_error("document_file", parse_err)

            if not doc_instance and not self.errors.get("document_file"):
                self.add_error("document_file", "Please upload a question document (PDF, DOCX, or TXT).")

            questions_to_use = []
            if payload_str and payload_str.strip():
                try:
                    payload = json.loads(payload_str)
                    for item in payload:
                        if item.get("is_selected", True):
                            questions_to_use.append(item)
                except Exception as exc:
                    self.add_error("document_file", f"Invalid questions preview data: {exc}")
            elif doc_instance:
                if doc_instance.raw_text:
                    questions_to_use = parse_questions_from_text(doc_instance.raw_text)
                else:
                    success, parse_err, parsed_qs = process_uploaded_document(doc_instance)
                    if success:
                        questions_to_use = parsed_qs
                    else:
                        self.add_error("document_file", parse_err)

            if not questions_to_use and not self.errors.get("document_file"):
                self.add_error("document_file", "No questions are selected or available in the document.")

            # Validate each MCQ question has an answer
            for idx, q in enumerate(questions_to_use, start=1):
                q_type = q.get("type", "MCQ")
                if q_type == "MCQ":
                    ans = (q.get("correct_answer") or "").strip().upper()
                    if ans not in ("A", "B", "C", "D"):
                        q_num = q.get("number", idx)
                        self.add_error(
                            "document_file",
                            f"Question {q_num} requires a correct answer. Please specify Option A, B, C, or D before creating the assessment.",
                        )
                        break

            total_doc_questions = len(questions_to_use)
            requested_count = cleaned_data.get("document_question_count")
            if requested_count is None or requested_count <= 0:
                requested_count = total_doc_questions

            if requested_count > total_doc_questions:
                self.add_error(
                    "document_question_count",
                    f"Only {total_doc_questions} questions are available in the uploaded document. Please upload a document containing at least {requested_count} questions.",
                )

            cleaned_data["document_question_count"] = requested_count
            cleaned_data["verified_document_questions"] = questions_to_use
            cleaned_data["assessment_document"] = doc_instance

        else:
            # question_source == "BANK" (existing flow)
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