"""Comprehensive Django unit and integration tests for the Admin Management Portal."""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import CandidateProfile, EmployerProfile
from assessments.models import (
    Assessment,
    AssessmentGroup,
    CodingQuestion,
    CodingTestCase,
    Question,
)
from dashboard.models import AdminActivityLog
from results.models import Result


class AdminPortalTestSuite(TestCase):
    """Test suite covering permissions, Question Bank CRUD, assessments, campaigns, analytics, proctoring, and exports."""

    def setUp(self):
        self.client = Client()

        # 1. Superuser / Admin
        self.admin_user = User.objects.create_superuser(
            username="superadmin",
            email="admin@platform.com",
            password="adminpassword123",
        )

        # 2. Employer 1
        self.employer_user1 = User.objects.create_user(
            username="employer1",
            email="employer1@company.com",
            password="employerpassword123",
        )
        self.employer_profile1 = EmployerProfile.objects.create(
            user=self.employer_user1,
            company="Tech Corp A",
        )

        # 3. Employer 2
        self.employer_user2 = User.objects.create_user(
            username="employer2",
            email="employer2@company.com",
            password="employerpassword123",
        )
        self.employer_profile2 = EmployerProfile.objects.create(
            user=self.employer_user2,
            company="Tech Corp B",
        )

        # 4. Candidate
        self.candidate_user = User.objects.create_user(
            username="candidate1",
            email="candidate1@mail.com",
            password="candidatepassword123",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            phone="9876543210",
            education="B.Tech Computer Science",
            experience=2,
            skills="Python, Django, SQL",
            profile_completed=True,
        )

        # 5. Questions (MCQ & Coding)
        self.mcq1 = Question.objects.create(
            section=Question.Sections.TECHNICAL,
            category="Python",
            difficulty=Question.Difficulties.MEDIUM,
            question_text="What is a Python generator?",
            option_a="A function that yields values",
            option_b="A hardware component",
            option_c="A compiler optimization",
            option_d="A CSS property",
            correct_answer="A",
            explanation="Generators use yield to produce a sequence lazily.",
            source_type=Question.SourceTypes.ADMIN_CREATED,
            is_active=True,
        )

        self.coding1 = CodingQuestion.objects.create(
            title="Two Sum Problem",
            slug="two-sum-problem",
            category=CodingQuestion.Categories.ARRAYS,
            difficulty=Question.Difficulties.EASY,
            description="Find indices of two numbers that add up to target.",
            input_format="Array and target integer",
            output_format="Indices array",
            sample_input="[2, 7, 11, 15], 9",
            sample_output="[0, 1]",
            source_type=Question.SourceTypes.CURATED,
            is_active=True,
        )
        CodingTestCase.objects.create(
            question=self.coding1,
            input_data="[2, 7, 11, 15], 9",
            expected_output="[0, 1]",
            is_sample=True,
            order=1,
        )

        # 6. Campaign & Assessment
        now = timezone.now()
        self.campaign1 = AssessmentGroup.objects.create(
            employer=self.employer_user1,
            title="Graduate Hiring 2026",
            start_time=now - timedelta(hours=1),
            expire_time=now + timedelta(hours=5),
            duration_minutes=60,
        )
        self.assessment1 = Assessment.objects.create(
            group=self.campaign1,
            employer=self.employer_user1,
            candidate=self.candidate_user,
            title="Graduate Assessment — Candidate 1",
            start_time=now - timedelta(hours=1),
            expire_time=now + timedelta(hours=5),
            duration_minutes=60,
            status=Assessment.Status.COMPLETED,
            candidate_status=Assessment.CandidateStatus.ATTENDED,
            violation_count=1,
            last_violation_type="TAB_SWITCH",
        )
        self.result1 = Result.objects.create(
            assessment=self.assessment1,
            aptitude_score=80.0,
            coding_score=90.0,
            overall_score=85.0,
            total_questions=1,
            total_correct=1,
            completed_at=now,
        )

    # -------------------------------------------------------------------------
    # Test 1, 2, 3, 18: Role Boundaries & Permissions
    # -------------------------------------------------------------------------

    def test_admin_can_access_admin_dashboard(self):
        """Admin can access the Admin Portal Overview."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("dashboard:admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "System Overview & Telemetry")
        self.assertContains(response, "Tech Corp A")

    def test_employer_cannot_access_admin_dashboard(self):
        """Employer is rejected from accessing the Admin Portal with PermissionDenied (403)."""
        self.client.force_login(self.employer_user1)
        response = self.client.get(reverse("dashboard:admin_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_candidate_cannot_access_admin_dashboard(self):
        """Candidate is rejected from accessing the Admin Portal with PermissionDenied (403)."""
        self.client.force_login(self.candidate_user)
        response = self.client.get(reverse("dashboard:admin_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_redirected_from_admin_portal(self):
        """Anonymous user is redirected to admin login."""
        response = self.client.get(reverse("dashboard:admin_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:admin_login"), response.url)

    def test_admin_portal_footer_link_exists(self):
        """Admin Login footer link points directly to accounts:admin_login, not admin_dashboard."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("accounts:admin_login"))
        self.assertContains(response, "Admin Login")
        self.assertNotContains(response, f'href="{reverse("dashboard:admin_dashboard")}"')

    def test_admin_can_login_via_admin_login_page(self):
        """Admin can log in through the dedicated Admin Login portal."""
        # 1. GET admin login page
        res_get = self.client.get(reverse("accounts:admin_login"))
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, "Admin Portal")
        self.assertContains(res_get, "Authorized administrators only.")

        # 2. POST valid admin credentials
        res_post = self.client.post(
            reverse("accounts:admin_login"),
            {"username": "admin@platform.com", "password": "adminpassword123"},
        )
        self.assertEqual(res_post.status_code, 302)
        self.assertRedirects(res_post, reverse("dashboard:admin_dashboard"))

        # 3. Access Admin Portal
        res_dash = self.client.get(reverse("dashboard:admin_dashboard"))
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, "System Overview & Telemetry")

    def test_non_admin_cannot_login_via_admin_login_page(self):
        """Non-admin candidates and employers cannot log in through the Admin Login page."""
        res_cand = self.client.post(
            reverse("accounts:admin_login"),
            {"username": "candidate1@mail.com", "password": "candidatepassword123"},
        )
        self.assertEqual(res_cand.status_code, 200)
        self.assertContains(res_cand, "Access denied")

    def test_invalid_admin_login_fails_safely(self):
        """Invalid passwords or non-existent usernames fail with a clean error message."""
        # Non-existent user
        res_nonexistent = self.client.post(
            reverse("accounts:admin_login"),
            {"username": "nonexistent@admin.com", "password": "WrongPassword!"},
        )
        self.assertEqual(res_nonexistent.status_code, 200)
        self.assertContains(res_nonexistent, "Invalid credentials")

        # Wrong password for existing admin
        res_wrong_pw = self.client.post(
            reverse("accounts:admin_login"),
            {"username": "admin@platform.com", "password": "WrongPassword!"},
        )
        self.assertEqual(res_wrong_pw.status_code, 200)
        self.assertContains(res_wrong_pw, "Invalid credentials")

    def test_admin_logout_and_portal_access_revoked(self):
        """Admin logout terminates session and blocks further access to the Admin Portal."""
        # 1. Log in admin
        self.client.post(
            reverse("accounts:admin_login"),
            {"username": "admin@platform.com", "password": "adminpassword123"},
        )
        # Verify authenticated access
        res_auth = self.client.get(reverse("dashboard:admin_dashboard"))
        self.assertEqual(res_auth.status_code, 200)

        # 2. Log out
        res_logout = self.client.post(reverse("accounts:candidate_logout"))
        self.assertEqual(res_logout.status_code, 302)

        # 3. Verify access is revoked and redirected to admin login
        res_after = self.client.get(reverse("dashboard:admin_dashboard"))
        self.assertEqual(res_after.status_code, 302)
        self.assertIn(reverse("accounts:admin_login"), res_after.url)

    def test_candidate_login_and_registration_still_work(self):
        """Candidate registration and login continue working without regression."""
        # Register new candidate
        reg_res = self.client.post(reverse("accounts:candidate_register"), {
            "name": "New Candidate",
            "email": "newcand@test.com",
            "password1": "CandidatePass123!",
            "password2": "CandidatePass123!",
        })
        self.assertEqual(reg_res.status_code, 302)

        # Login candidate
        login_res = self.client.post(reverse("accounts:candidate_login"), {
            "username": "newcand@test.com",
            "password": "CandidatePass123!",
        })
        self.assertEqual(login_res.status_code, 302)
        self.assertRedirects(login_res, reverse("candidates:candidate_dashboard"))

    def test_employer_login_and_registration_still_work(self):
        """Employer registration and login continue working without regression."""
        # Register new employer
        reg_res = self.client.post(reverse("accounts:employer_register"), {
            "name": "New Employer",
            "email": "newemp@company.com",
            "company": "New Corp Inc",
            "password1": "EmployerPass123!",
            "password2": "EmployerPass123!",
        })
        self.assertEqual(reg_res.status_code, 302)

        # Login employer
        login_res = self.client.post(reverse("accounts:employer_login"), {
            "username": "newemp@company.com",
            "password": "EmployerPass123!",
        })
        self.assertEqual(login_res.status_code, 302)
        self.assertRedirects(login_res, reverse("dashboard:employer_dashboard"))

    # -------------------------------------------------------------------------
    # Test 4 & 5: Admin Platform-wide User Visibility
    # -------------------------------------------------------------------------

    def test_admin_can_view_all_employers(self):
        """Admin can view the full employer directory."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("dashboard:admin_employers_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "employer1")
        self.assertContains(response, "employer2")
        self.assertContains(response, "Tech Corp A")
        self.assertContains(response, "Tech Corp B")

    def test_admin_can_view_all_candidates(self):
        """Admin can view all registered candidates."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("dashboard:admin_candidates_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "candidate1")
        self.assertContains(response, "candidate1@mail.com")

    # -------------------------------------------------------------------------
    # Test 8: MCQ Question CRUD
    # -------------------------------------------------------------------------

    def test_admin_mcq_crud(self):
        """Admin can Create, Read, Update, and Safely Deactivate MCQ questions."""
        self.client.force_login(self.admin_user)

        # CREATE
        create_data = {
            "section": Question.Sections.LOGICAL,
            "category": "Number Series",
            "difficulty": Question.Difficulties.EASY,
            "question_text": "Find next in series: 2, 4, 8, 16, ?",
            "option_a": "32",
            "option_b": "30",
            "option_c": "24",
            "option_d": "64",
            "correct_answer": "A",
            "explanation": "Each number is multiplied by 2.",
            "source_type": Question.SourceTypes.ADMIN_CREATED,
            "ai_provider": "Manual Editorial",
            "is_reviewed": True,
            "is_approved": True,
            "is_active": True,
        }
        res = self.client.post(reverse("dashboard:admin_mcq_create"), data=create_data)
        self.assertEqual(res.status_code, 302)
        new_q = Question.objects.get(question_text="Find next in series: 2, 4, 8, 16, ?")
        self.assertEqual(new_q.correct_answer, "A")
        self.assertTrue(new_q.is_active)

        # UPDATE
        edit_data = create_data.copy()
        edit_data["category"] = "Geometric Progressions"
        res_edit = self.client.post(reverse("dashboard:admin_mcq_edit", args=[new_q.id]), data=edit_data)
        self.assertEqual(res_edit.status_code, 302)
        new_q.refresh_from_db()
        self.assertEqual(new_q.category, "Geometric Progressions")

        # TOGGLE ACTIVE
        res_toggle = self.client.post(reverse("dashboard:admin_question_toggle", args=["mcq", new_q.id]))
        self.assertEqual(res_toggle.status_code, 302)
        new_q.refresh_from_db()
        self.assertFalse(new_q.is_active)

        # DELETE (Unused question deleted permanently)
        res_del = self.client.post(reverse("dashboard:admin_question_delete", args=["mcq", new_q.id]))
        self.assertEqual(res_del.status_code, 302)
        self.assertFalse(Question.objects.filter(id=new_q.id).exists())

    # -------------------------------------------------------------------------
    # Test 9: Coding Question CRUD
    # -------------------------------------------------------------------------

    def test_admin_coding_crud(self):
        """Admin can Create, Read, Update, and Manage Coding challenges."""
        self.client.force_login(self.admin_user)

        # CREATE
        create_data = {
            "title": "Reverse String In-Place",
            "slug": "reverse-string-in-place",
            "category": CodingQuestion.Categories.STRINGS,
            "difficulty": Question.Difficulties.EASY,
            "description": "Reverse a given character array in O(1) extra memory.",
            "input_format": "List of chars",
            "output_format": "Reversed list of chars",
            "sample_input": "hello",
            "sample_output": "olleh",
            "time_limit_seconds": 2,
            "memory_limit_mb": 256,
            "max_score": 100,
            "source_type": Question.SourceTypes.ADMIN_CREATED,
            "is_reviewed": True,
            "is_approved": True,
            "is_active": True,
            "tc_input[]": ["hello", "world"],
            "tc_output[]": ["olleh", "dlrow"],
            "tc_is_sample[]": ["0"],
        }
        res = self.client.post(reverse("dashboard:admin_coding_create"), data=create_data)
        self.assertEqual(res.status_code, 302)
        cq = CodingQuestion.objects.get(title="Reverse String In-Place")
        self.assertEqual(cq.test_cases.count(), 2)

        # UPDATE
        edit_data = create_data.copy()
        edit_data["difficulty"] = Question.Difficulties.MEDIUM
        res_edit = self.client.post(reverse("dashboard:admin_coding_edit", args=[cq.id]), data=edit_data)
        self.assertEqual(res_edit.status_code, 302)
        cq.refresh_from_db()
        self.assertEqual(cq.difficulty, Question.Difficulties.MEDIUM)

    # -------------------------------------------------------------------------
    # Test 10: Bulk Question Actions
    # -------------------------------------------------------------------------

    def test_admin_bulk_question_actions(self):
        """Admin can bulk activate and deactivate selected questions safely."""
        self.client.force_login(self.admin_user)
        self.assertTrue(self.mcq1.is_active)
        self.assertTrue(self.coding1.is_active)

        # Bulk Deactivate
        data_deact = {
            "bulk_action": "deactivate",
            "selected_questions": [f"mcq_{self.mcq1.id}", f"coding_{self.coding1.id}"],
        }
        res = self.client.post(reverse("dashboard:admin_questions_bulk_action"), data=data_deact)
        self.assertEqual(res.status_code, 302)
        self.mcq1.refresh_from_db()
        self.coding1.refresh_from_db()
        self.assertFalse(self.mcq1.is_active)
        self.assertFalse(self.coding1.is_active)

        # Bulk Activate
        data_act = {
            "bulk_action": "activate",
            "selected_questions": [f"mcq_{self.mcq1.id}", f"coding_{self.coding1.id}"],
        }
        res_act = self.client.post(reverse("dashboard:admin_questions_bulk_action"), data=data_act)
        self.assertEqual(res_act.status_code, 302)
        self.mcq1.refresh_from_db()
        self.coding1.refresh_from_db()
        self.assertTrue(self.mcq1.is_active)
        self.assertTrue(self.coding1.is_active)

    # -------------------------------------------------------------------------
    # Test 11 & 12: Assessments & Campaigns Platform-wide Management
    # -------------------------------------------------------------------------

    def test_admin_assessments_management(self):
        """Admin can view all assessments and inspect individual assessment detail."""
        self.client.force_login(self.admin_user)
        res_list = self.client.get(reverse("dashboard:admin_assessments"))
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, self.assessment1.title)

        res_detail = self.client.get(reverse("dashboard:admin_assessment_detail", args=[self.assessment1.id]))
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, "Assessment Inspection")
        self.assertContains(res_detail, "85")

    def test_admin_campaigns_management(self):
        """Admin can view all campaigns across employers and drill down into cohorts."""
        self.client.force_login(self.admin_user)
        res_list = self.client.get(reverse("dashboard:admin_campaigns"))
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, self.campaign1.title)

        res_cohort = self.client.get(reverse("dashboard:admin_campaign_detail", args=[self.campaign1.id]))
        self.assertEqual(res_cohort.status_code, 200)
        self.assertContains(res_cohort, "Cohort breakdown")
        self.assertContains(res_cohort, self.candidate_user.username)

    # -------------------------------------------------------------------------
    # Test 13 & 14: Results & Proctoring Visibility
    # -------------------------------------------------------------------------

    def test_admin_results_analytics(self):
        """Admin can view platform-wide analytics and export results."""
        self.client.force_login(self.admin_user)
        res = self.client.get(reverse("dashboard:admin_analytics"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "85.0%")

        # CSV Export
        res_csv = self.client.get(reverse("dashboard:admin_results_csv_export"))
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv["Content-Type"], "text/csv")
        self.assertIn(b"candidate1@mail.com", res_csv.content)

    def test_admin_proctoring_telemetry(self):
        """Admin can view platform-wide malpractice telemetry."""
        self.client.force_login(self.admin_user)
        res = self.client.get(reverse("dashboard:admin_proctoring"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "TAB_SWITCH")
        self.assertContains(res, "1/3")

    # -------------------------------------------------------------------------
    # Test 15 & 16: AI Management & Admin Activity Logs
    # -------------------------------------------------------------------------

    def test_admin_ai_governance(self):
        """Admin can view AI provenance and decision-support heuristics."""
        self.client.force_login(self.admin_user)
        res = self.client.get(reverse("dashboard:admin_ai_management"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "AI Decision Support & Governance Policy")

    def test_admin_activity_audit_logs(self):
        """Admin actions are recorded in AdminActivityLog and viewable in audit trail."""
        self.client.force_login(self.admin_user)
        # Create an action
        self.client.post(reverse("dashboard:admin_question_toggle", args=["mcq", self.mcq1.id]))
        
        # Verify log entry
        logs = AdminActivityLog.objects.all()
        self.assertTrue(logs.exists())

        res = self.client.get(reverse("dashboard:admin_activity_logs"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Audit Log Records")

    # -------------------------------------------------------------------------
    # Test 17: Platform Reports CSV Generators
    # -------------------------------------------------------------------------

    def test_admin_reports_exports(self):
        """Admin can access reports landing page and generate all 5 CSV exports."""
        self.client.force_login(self.admin_user)
        res_landing = self.client.get(reverse("dashboard:admin_reports"))
        self.assertEqual(res_landing.status_code, 200)

        # Candidates CSV
        res_cand = self.client.get(reverse("dashboard:admin_export_candidates_csv"))
        self.assertEqual(res_cand.status_code, 200)
        self.assertIn(b"candidate1@mail.com", res_cand.content)

        # Employers CSV
        res_emp = self.client.get(reverse("dashboard:admin_export_employers_csv"))
        self.assertEqual(res_emp.status_code, 200)
        self.assertIn(b"Tech Corp A", res_emp.content)

        # Assessments CSV
        res_ass = self.client.get(reverse("dashboard:admin_export_assessments_csv"))
        self.assertEqual(res_ass.status_code, 200)
        self.assertIn(b"Graduate Assessment", res_ass.content)

        # Questions CSV
        res_q = self.client.get(reverse("dashboard:admin_export_questions_csv"))
        self.assertEqual(res_q.status_code, 200)
        self.assertIn(b"What is a Python generator?", res_q.content)

        # Proctoring CSV
        res_proc = self.client.get(reverse("dashboard:admin_export_proctoring_csv"))
        self.assertEqual(res_proc.status_code, 200)
        self.assertIn(b"TAB_SWITCH", res_proc.content)

    # -------------------------------------------------------------------------
    # Test 19: Search & Filter Verification
    # -------------------------------------------------------------------------

    def test_search_and_filters(self):
        """Admin Question Bank, Assessments, and Proctoring search/filters return expected records."""
        self.client.force_login(self.admin_user)

        # Question Search
        res_q = self.client.get(reverse("dashboard:admin_questions"), {"q": "Python generator"})
        self.assertEqual(res_q.status_code, 200)
        self.assertContains(res_q, "What is a Python generator?")

        # Assessment Filter
        res_ass = self.client.get(reverse("dashboard:admin_assessments"), {"status": "COMPLETED"})
        self.assertEqual(res_ass.status_code, 200)
        self.assertContains(res_ass, self.assessment1.title)

        # Proctoring Filter
        res_proc = self.client.get(reverse("dashboard:admin_proctoring"), {"flagged": "yes"})
        self.assertEqual(res_proc.status_code, 200)
        self.assertContains(res_proc, self.candidate_user.username)
