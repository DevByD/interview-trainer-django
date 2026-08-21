from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("employer/dashboard/", views.employer_dashboard, name="employer_dashboard"),
    path("employer/candidates/", views.employer_candidates_list, name="employer_candidates_list"),
    path("employer/candidates/<int:candidate_id>/", views.employer_candidate_detail, name="employer_candidate_detail"),
]
