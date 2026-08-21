from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from .models import CandidateProfile, EmployerProfile


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "phone",
        "education",
        "experience",
        "profile_completed",
        "email_verified",
        "created_at",
    )
    search_fields = ("user__username", "user__email", "phone", "education", "skills")
    list_filter = ("profile_completed", "email_verified", "experience")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "created_at")
    search_fields = ("user__username", "user__email", "company")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


class CandidateProfileInline(admin.StackedInline):
    model = CandidateProfile
    can_delete = False
    verbose_name_plural = "Candidate profile"


class EmployerProfileInline(admin.StackedInline):
    model = EmployerProfile
    can_delete = False
    verbose_name_plural = "Employer profile"


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [CandidateProfileInline, EmployerProfileInline]
