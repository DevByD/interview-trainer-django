"""URL routing for HumanDB integration endpoints."""

from django.urls import path
from . import views

app_name = "integration"

urlpatterns = [
    path("candidates/sync/", views.CandidateSyncView.as_view(), name="candidate_sync"),
    path("assessments/", views.AssessmentCreateView.as_view(), name="assessment_create"),
    path("assessments/<int:assessment_id>/", views.AssessmentDetailView.as_view(), name="assessment_detail"),
    path("results/<int:assessment_id>/", views.ResultDetailView.as_view(), name="result_detail"),
    path("results/callback/", views.ResultCallbackView.as_view(), name="result_callback"),
]
