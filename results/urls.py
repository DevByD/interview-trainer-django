from django.urls import path
from . import views

app_name = "results"

urlpatterns = [
    path("candidate/results/<int:result_id>/", views.candidate_result, name="candidate_result"),
    path("employer/results/<int:result_id>/", views.employer_result, name="employer_result"),
]
