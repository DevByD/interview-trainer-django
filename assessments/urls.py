from django.urls import path
from . import views

app_name = "assessments"

urlpatterns = [
    path("employer/assessments/create/", views.employer_assessment_create, name="employer_assessment_create"),
    path("employer/assessments/", views.employer_assessment_list, name="employer_assessment_list"),
    path("employer/campaigns/", views.employer_campaign_list, name="employer_campaign_list"),
    path("employer/campaign/<int:group_id>/", views.employer_campaign_detail, name="employer_campaign_detail"),
    path("employer/campaign/<int:group_id>/ai-shortlist/", views.employer_campaign_ai_shortlist, name="employer_campaign_ai_shortlist"),
    path("employer/campaign/<int:group_id>/shortlist-action/", views.employer_campaign_shortlist_action, name="employer_campaign_shortlist_action"),
    path("employer/questions/generate/", views.employer_ai_question_generator, name="employer_ai_question_generator"),

    path("test/<str:token>/", views.test_entry, name="test_entry"),
    path("test/<str:token>/start/", views.test_start, name="test_start"),
    path("test/<str:token>/save-answer/", views.test_save_answer, name="test_save_answer"),
    path("test/<str:token>/submit/", views.test_submit, name="test_submit"),
    path("test/<str:token>/coding/", views.test_coding, name="test_coding"),
    path("test/<str:token>/coding/save/", views.test_save_code, name="test_save_code"),
    path("test/<str:token>/coding/run/", views.test_run_code, name="test_run_code"),
    path("test/<str:token>/coding/submit-problem/", views.test_submit_code_problem, name="test_submit_code_problem"),
    path("test/<str:token>/violation/", views.test_record_violation, name="test_violation"),
    path("api/cron/expire-assessments/", views.cron_expire_assessments, name="cron_expire_assessments"),
]