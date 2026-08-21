from django.urls import path

from . import views

app_name = "candidates"

urlpatterns = [
    path("dashboard/", views.dashboard, name="candidate_dashboard"),
    path("profile/", views.profile, name="candidate_profile"),
]
