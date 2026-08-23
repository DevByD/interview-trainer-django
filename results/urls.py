from django.urls import path
from . import views

app_name = "results"

urlpatterns = [
    path("candidate/results/<int:result_id>/", views.candidate_result, name="candidate_result"),
    path("employer/results/<int:result_id>/", views.employer_result, name="employer_result"),
    path("employer/results/<int:result_id>/export-csv/", views.employer_result_csv_export, name="employer_result_csv_export"),
    path("employer/results/export-all-csv/", views.employer_all_results_csv_export, name="employer_all_results_csv_export"),
]

