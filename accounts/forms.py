"""Registration forms for candidates and employers.

Passwords are handled exclusively by Django's UserCreationForm machinery
(PBKDF2 hashing + password strength validation). No plaintext password is ever stored.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import CandidateProfile, EmployerProfile


class CandidateRegisterForm(UserCreationForm):
    name = forms.CharField(
        max_length=150,
        required=True,
        label="Full Name",
        widget=forms.TextInput(
            attrs={"placeholder": "Enter your full name", "class": "form-input", "autocomplete": "name"}
        ),
    )
    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(
            attrs={"placeholder": "you@example.com", "class": "form-input", "autocomplete": "email"}
        ),
    )

    class Meta:
        model = User
        fields = ("name", "email")

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        name = self.cleaned_data.get("name", "").strip()
        if name:
            parts = name.split(None, 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
        email = self.cleaned_data.get("email", "").strip().lower()
        user.email = email
        user.username = email
        if commit:
            user.save()
            CandidateProfile.objects.get_or_create(user=user)
        return user


class EmployerRegisterForm(UserCreationForm):
    name = forms.CharField(
        max_length=150,
        required=True,
        label="Full Name",
        widget=forms.TextInput(
            attrs={"placeholder": "Enter your full name", "class": "form-input", "autocomplete": "name"}
        ),
    )
    email = forms.EmailField(
        required=True,
        label="Work Email Address",
        widget=forms.EmailInput(
            attrs={"placeholder": "recruiter@company.com", "class": "form-input", "autocomplete": "email"}
        ),
    )
    company = forms.CharField(
        max_length=200,
        required=True,
        label="Company / Organization",
        widget=forms.TextInput(
            attrs={"placeholder": "Acme Technologies Pvt. Ltd.", "class": "form-input"}
        ),
    )

    class Meta:
        model = User
        fields = ("name", "email", "company")

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email address already exists.")
        return email

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        name = self.cleaned_data.get("name", "").strip()
        if name:
            parts = name.split(None, 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
        email = self.cleaned_data.get("email", "").strip().lower()
        user.email = email
        user.username = email
        if commit:
            user.save()
            EmployerProfile.objects.get_or_create(
                user=user,
                defaults={"company": self.cleaned_data.get("company", "").strip()},
            )
        return user
