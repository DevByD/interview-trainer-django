from django.urls import path
from . import admin_views, views

app_name = "dashboard"

urlpatterns = [
    # Employer Dashboard Routes
    path("employer/dashboard/", views.employer_dashboard, name="employer_dashboard"),
    path("employer/candidates/", views.employer_candidates_list, name="employer_candidates_list"),
    path("employer/candidates/<int:candidate_id>/", views.employer_candidate_detail, name="employer_candidate_detail"),

    # Admin Management Portal Routes
    path("admin-portal/", admin_views.admin_dashboard, name="admin_dashboard"),
    path("admin-portal/questions/", admin_views.admin_questions_list, name="admin_questions"),
    path("admin-portal/questions/create/mcq/", admin_views.admin_mcq_create, name="admin_mcq_create"),
    path("admin-portal/questions/<int:question_id>/edit/mcq/", admin_views.admin_mcq_edit, name="admin_mcq_edit"),
    path("admin-portal/questions/create/coding/", admin_views.admin_coding_create, name="admin_coding_create"),
    path("admin-portal/questions/<int:question_id>/edit/coding/", admin_views.admin_coding_edit, name="admin_coding_edit"),
    path("admin-portal/questions/<str:q_type>/<int:question_id>/toggle/", admin_views.admin_question_toggle_active, name="admin_question_toggle"),
    path("admin-portal/questions/<str:q_type>/<int:question_id>/delete/", admin_views.admin_question_delete, name="admin_question_delete"),
    path("admin-portal/questions/bulk-action/", admin_views.admin_questions_bulk_action, name="admin_questions_bulk_action"),
    path("admin-portal/assessments/", admin_views.admin_assessments_list, name="admin_assessments"),
    path("admin-portal/assessments/<int:assessment_id>/", admin_views.admin_assessment_detail, name="admin_assessment_detail"),
    path("admin-portal/campaigns/", admin_views.admin_campaigns_list, name="admin_campaigns"),
    path("admin-portal/campaigns/<int:campaign_id>/", admin_views.admin_campaign_detail, name="admin_campaign_detail"),
    path("admin-portal/analytics/", admin_views.admin_results_analytics, name="admin_analytics"),
    path("admin-portal/analytics/export-csv/", admin_views.admin_results_csv_export, name="admin_results_csv_export"),
    path("admin-portal/proctoring/", admin_views.admin_proctoring_dashboard, name="admin_proctoring"),
    path("admin-portal/ai/", admin_views.admin_ai_management, name="admin_ai_management"),
    path("admin-portal/activity-logs/", admin_views.admin_activity_logs, name="admin_activity_logs"),
    path("admin-portal/reports/", admin_views.admin_reports, name="admin_reports"),
    path("admin-portal/reports/export/candidates/", admin_views.admin_export_candidates_csv, name="admin_export_candidates_csv"),
    path("admin-portal/reports/export/employers/", admin_views.admin_export_employers_csv, name="admin_export_employers_csv"),
    path("admin-portal/reports/export/assessments/", admin_views.admin_export_assessments_csv, name="admin_export_assessments_csv"),
    path("admin-portal/reports/export/questions/", admin_views.admin_export_questions_csv, name="admin_export_questions_csv"),
    path("admin-portal/reports/export/proctoring/", admin_views.admin_export_proctoring_csv, name="admin_export_proctoring_csv"),
    path("admin-portal/candidates/", admin_views.admin_candidates_list, name="admin_candidates_list"),
    path("admin-portal/employers/", admin_views.admin_employers_list, name="admin_employers_list"),
    path("admin-portal/employers/<int:user_id>/toggle/", admin_views.admin_employer_toggle_active, name="admin_employer_toggle"),
]
