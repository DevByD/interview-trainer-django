from io import BytesIO
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta

from accounts.models import CandidateProfile, EmployerProfile
from assessments.models import Assessment, Question, AssessmentQuestion, Answer
from results.models import Result


class Phase1ValidationTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_01_landing_page(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Smarter Interview Assessments")
        self.assertContains(response, "Candidate Register")
        self.assertContains(response, "Employer Register")

    def test_02_candidate_registration_and_login(self):
        # Register
        reg_data = {
            "name": "Alex Candidate",
            "email": "alex@example.com",
            "password1": "CandidatePass123!",
            "password2": "CandidatePass123!",
        }
        res = self.client.post(reverse("accounts:candidate_register"), data=reg_data)
        self.assertEqual(res.status_code, 302)

        # Verify candidate created
        user = User.objects.get(email="alex@example.com")
        self.assertEqual(user.first_name, "Alex")
        self.assertTrue(hasattr(user, "candidate_profile"))
        self.assertFalse(hasattr(user, "employer_profile"))

        # Logout
        self.client.post(reverse("accounts:candidate_logout"))

        # Login with email
        login_res = self.client.post(reverse("accounts:candidate_login"), {
            "username": "alex@example.com",
            "password": "CandidatePass123!",
        })
        self.assertEqual(login_res.status_code, 302)

        # Access candidate dashboard
        dash_res = self.client.get(reverse("candidates:candidate_dashboard"))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "Alex")

    def test_03_candidate_profile_update(self):
        user = User.objects.create_user(username="cand@example.com", email="cand@example.com", password="Password123!")
        profile = CandidateProfile.objects.create(user=user)
        self.client.login(username="cand@example.com", password="Password123!")

        # Check initial completion percentage
        self.assertLess(profile.completion_percentage, 100)

        # Upload dummy resume
        resume_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 dummy resume content", content_type="application/pdf")
        update_data = {
            "name": "Updated Candidate Name",
            "phone": "+919876543210",
            "education": "B.Tech Computer Science",
            "skills": "Python, Django, SQL",
            "experience": 3,
            "resume": resume_file,
        }
        res = self.client.post(reverse("candidates:candidate_profile"), data=update_data)
        self.assertEqual(res.status_code, 302)

        profile.refresh_from_db()
        self.assertEqual(profile.phone, "+919876543210")
        self.assertEqual(profile.education, "B.Tech Computer Science")
        self.assertTrue(profile.profile_completed)
        self.assertEqual(profile.completion_percentage, 100)

    def test_04_employer_registration_and_dashboard(self):
        reg_data = {
            "name": "Jane Recruiter",
            "email": "jane@techcorp.com",
            "company": "TechCorp Global",
            "password1": "EmployerPass123!",
            "password2": "EmployerPass123!",
        }
        res = self.client.post(reverse("accounts:employer_register"), data=reg_data)
        self.assertEqual(res.status_code, 302)

        user = User.objects.get(email="jane@techcorp.com")
        self.assertEqual(user.first_name, "Jane")
        self.assertTrue(hasattr(user, "employer_profile"))
        self.assertEqual(user.employer_profile.company, "TechCorp Global")

        # Employer dashboard access
        dash_res = self.client.get(reverse("dashboard:employer_dashboard"))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "TechCorp Global")

    def test_05_employer_candidate_management(self):
        # Create candidate
        cand_user = User.objects.create_user(username="cand2@test.com", email="cand2@test.com", password="Password123!", first_name="Bob")
        cand_prof = CandidateProfile.objects.create(user=cand_user, phone="123456", education="MCA", skills="Django, REST")

        # Create employer & login
        emp_user = User.objects.create_user(username="emp2@test.com", email="emp2@test.com", password="Password123!")
        EmployerProfile.objects.create(user=emp_user, company="Acme Inc")
        self.client.login(username="emp2@test.com", password="Password123!")

        # Candidates directory
        list_res = self.client.get(reverse("dashboard:employer_candidates_list"))
        self.assertEqual(list_res.status_code, 200)
        self.assertContains(list_res, "Bob")
        self.assertContains(list_res, "MCA")

        # Candidate detail
        detail_res = self.client.get(reverse("dashboard:employer_candidate_detail", kwargs={"candidate_id": cand_prof.id}))
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, "cand2@test.com")
        self.assertContains(detail_res, "Django, REST")

    def test_06_role_based_access_control(self):
        # Candidate tries to access employer dashboard
        cand_user = User.objects.create_user(username="cand_sec@test.com", email="cand_sec@test.com", password="Password123!")
        CandidateProfile.objects.create(user=cand_user)
        self.client.login(username="cand_sec@test.com", password="Password123!")

        emp_dash_res = self.client.get(reverse("dashboard:employer_dashboard"))
        self.assertEqual(emp_dash_res.status_code, 302) # Redirected away

        emp_cand_res = self.client.get(reverse("dashboard:employer_candidates_list"))
        self.assertEqual(emp_cand_res.status_code, 302) # Redirected away

        # Employer tries to access candidate dashboard & profile
        emp_user = User.objects.create_user(username="emp_sec@test.com", email="emp_sec@test.com", password="Password123!")
        EmployerProfile.objects.create(user=emp_user, company="Sec Corp")
        self.client.login(username="emp_sec@test.com", password="Password123!")

        cand_dash_res = self.client.get(reverse("candidates:candidate_dashboard"))
        self.assertEqual(cand_dash_res.status_code, 302) # Redirected away

        cand_prof_res = self.client.get(reverse("candidates:candidate_profile"))
        self.assertEqual(cand_prof_res.status_code, 302) # Redirected away
