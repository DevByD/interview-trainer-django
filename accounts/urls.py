from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Candidate auth
    path("candidate/register/", views.candidate_register, name="candidate_register"),
    path("candidate/login/", views.candidate_login, name="candidate_login"),
    path("candidate/logout/", views.logout_view, name="candidate_logout"),
    # Employer auth
    path("employer/register/", views.employer_register, name="employer_register"),
    path("employer/login/", views.employer_login, name="employer_login"),
    path("employer/logout/", views.logout_view, name="employer_logout"),
]
