"""Admin forms for Question Bank CRUD and management."""

from django import forms
from django.utils.text import slugify

from assessments.models import CodingQuestion, CodingTestCase, Question


class MCQQuestionForm(forms.ModelForm):
    """Form for creating and editing MCQ questions in the admin portal."""

    class Meta:
        model = Question
        fields = [
            "section",
            "category",
            "difficulty",
            "question_text",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_answer",
            "explanation",
            "source_type",
            "ai_provider",
            "is_reviewed",
            "is_approved",
            "is_active",
        ]
        widgets = {
            "section": forms.Select(attrs={"class": "form-control"}),
            "category": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Number Series, Data Interpretation, Python"}),
            "difficulty": forms.Select(attrs={"class": "form-control"}),
            "question_text": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Enter the question prompt..."}),
            "option_a": forms.TextInput(attrs={"class": "form-control", "placeholder": "Option A"}),
            "option_b": forms.TextInput(attrs={"class": "form-control", "placeholder": "Option B"}),
            "option_c": forms.TextInput(attrs={"class": "form-control", "placeholder": "Option C"}),
            "option_d": forms.TextInput(attrs={"class": "form-control", "placeholder": "Option D"}),
            "correct_answer": forms.Select(attrs={"class": "form-control"}),
            "explanation": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Explanation of the correct answer and solution methodology..."}),
            "source_type": forms.Select(attrs={"class": "form-control"}),
            "ai_provider": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Google Gemini 1.5, Manual Editorial"}),
            "is_reviewed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_approved": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["source_type"].initial = Question.SourceTypes.ADMIN_CREATED
            self.fields["is_reviewed"].initial = True
            self.fields["is_approved"].initial = True
            self.fields["is_active"].initial = True


class CodingQuestionForm(forms.ModelForm):
    """Form for creating and editing algorithmic coding challenges in the admin portal."""

    starter_code_py = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 4, "placeholder": "def solution(arr):\n    # Write code here\n    pass"}),
        label="Python Starter Code",
    )
    starter_code_java = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 4, "placeholder": "class Solution {\n    public int solve(int[] nums) {\n        return 0;\n    }\n}"}),
        label="Java Starter Code",
    )
    starter_code_cpp = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 4, "placeholder": "class Solution {\npublic:\n    int solve(vector<int>& nums) {\n        return 0;\n    }\n};"}),
        label="C++ Starter Code",
    )
    starter_code_js = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 4, "placeholder": "function solution(nums) {\n    return 0;\n}"}),
        label="JavaScript Starter Code",
    )

    class Meta:
        model = CodingQuestion
        fields = [
            "title",
            "slug",
            "category",
            "difficulty",
            "description",
            "input_format",
            "output_format",
            "constraints",
            "sample_input",
            "sample_output",
            "explanation",
            "time_limit_seconds",
            "memory_limit_mb",
            "max_score",
            "source_type",
            "ai_provider",
            "is_reviewed",
            "is_approved",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Two Sum"}),
            "slug": forms.TextInput(attrs={"class": "form-control", "placeholder": "two-sum"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "difficulty": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Detailed problem statement..."}),
            "input_format": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "First line contains N..."}),
            "output_format": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Return single integer..."}),
            "constraints": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "1 <= N <= 10^5"}),
            "sample_input": forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 2, "placeholder": "4\n2 7 11 15\n9"}),
            "sample_output": forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 2, "placeholder": "0 1"}),
            "explanation": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Because nums[0] + nums[1] == 9, return [0, 1]."}),
            "time_limit_seconds": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 30}),
            "memory_limit_mb": forms.NumberInput(attrs={"class": "form-control", "min": 64, "max": 1024}),
            "max_score": forms.NumberInput(attrs={"class": "form-control", "min": 10, "max": 500}),
            "source_type": forms.Select(attrs={"class": "form-control"}),
            "ai_provider": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Manual Editorial"}),
            "is_reviewed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_approved": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            sc = self.instance.starter_code or {}
            self.fields["starter_code_py"].initial = sc.get("python", "")
            self.fields["starter_code_java"].initial = sc.get("java", "")
            self.fields["starter_code_cpp"].initial = sc.get("cpp", "")
            self.fields["starter_code_js"].initial = sc.get("javascript", "")
        else:
            self.fields["source_type"].initial = Question.SourceTypes.ADMIN_CREATED
            self.fields["is_reviewed"].initial = True
            self.fields["is_approved"].initial = True
            self.fields["is_active"].initial = True

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        if not slug:
            title = self.cleaned_data.get("title", "")
            slug = slugify(title)
        return slug

    def save(self, commit=True):
        instance = super().save(commit=False)
        starter = {
            "python": self.cleaned_data.get("starter_code_py", ""),
            "java": self.cleaned_data.get("starter_code_java", ""),
            "cpp": self.cleaned_data.get("starter_code_cpp", ""),
            "javascript": self.cleaned_data.get("starter_code_js", ""),
        }
        instance.starter_code = starter
        if commit:
            instance.save()
        return instance
