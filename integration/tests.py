"""Comprehensive test suite for HumanDB Recruitment integration endpoints."""

import uuid
from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import CandidateProfile, EmployerProfile
from assessments.models import Assessment, CodingQuestion, Question
from integration.models import IntegrationSyncLog
from results.models import Result

TEST_API_KEY = "test-humandb-integration-secret-key-12345"


@override_settings(HUMANDB_INTEGRATION_API_KEY=TEST_API_KEY)
class HumanDBIntegrationTests(TestCase):
    """Test suite covering authentication, candidate synchronization, assessment creation, and result retrieval."""

    def setUp(self):
        self.client = APIClient()
        self.auth_headers = {"HTTP_X_HUMANDB_INTEGRATION_KEY": TEST_API_KEY}
        self.valid_uuid = str(uuid.uuid4())

        # Seed sample questions for assessment creation tests
        self.logical_q = Question.objects.create(
            section=Question.Sections.LOGICAL,
            question_text="What comes next in the sequence: 2, 4, 8, 16?",
            option_a="18",
            option_b="24",
            option_c="32",
            option_d="64",
            correct_answer="C",
            difficulty=Question.Difficulties.EASY,
            is_active=True,
            is_approved=True,
        )
        self.coding_q = CodingQuestion.objects.create(
            title="Two Sum Problem",
            slug="two-sum-problem",
            category=CodingQuestion.Categories.ARRAYS,
            description="Find two numbers that add up to target.",
            input_format="List and integer",
            output_format="Indices",
            sample_input="[2,7,11,15], 9",
            sample_output="[0,1]",
            is_active=True,
            is_approved=True,
        )

    # -------------------------------------------------------------------------
    # Authentication & Security Tests
    # -------------------------------------------------------------------------
    def test_missing_integration_key_rejected(self):
        """Requests without X-HumanDB-Integration-Key header must be rejected with 401."""
        response = self.client.post(
            "/api/integration/candidates/sync/",
            data={
                "human_db_user_id": self.valid_uuid,
                "email": "candidate@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.data)

    def test_invalid_integration_key_rejected(self):
        """Requests with an invalid integration key must be rejected with 401."""
        response = self.client.post(
            "/api/integration/candidates/sync/",
            data={
                "human_db_user_id": self.valid_uuid,
                "email": "candidate@example.com",
            },
            format="json",
            HTTP_X_HUMANDB_INTEGRATION_KEY="wrong-invalid-secret-key",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.data)

    def test_server_unconfigured_integration_key_rejected(self):
        """If server has no integration key configured, all requests must be securely rejected."""
        with override_settings(HUMANDB_INTEGRATION_API_KEY=""):
            response = self.client.post(
                "/api/integration/candidates/sync/",
                data={
                    "human_db_user_id": self.valid_uuid,
                    "email": "candidate@example.com",
                },
                format="json",
                HTTP_X_HUMANDB_INTEGRATION_KEY=TEST_API_KEY,
            )
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authentication_cannot_be_bypassed_via_candidate_session(self):
        """A candidate session cannot bypass the service-to-service authentication."""
        # Create candidate user and log in via Django session
        cand_user = User.objects.create_user(
            username="candidate_session_user",
            email="cand_session@example.com",
            password="testpassword123",
        )
        CandidateProfile.objects.create(user=cand_user)
        self.client.login(username="candidate_session_user", password="testpassword123")

        # Attempt to call integration endpoint without integration key
        response = self.client.post(
            "/api/integration/candidates/sync/",
            data={
                "human_db_user_id": self.valid_uuid,
                "email": "another@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -------------------------------------------------------------------------
    # Candidate Synchronization Tests
    # -------------------------------------------------------------------------
    def test_valid_candidate_sync_success(self):
        """Valid candidate payload creates Interview User and CandidateProfile with human_db_user_id."""
        payload = {
            "human_db_user_id": self.valid_uuid,
            "email": "alex.turner@example.com",
            "username": "alexturner",
            "first_name": "Alex",
            "last_name": "Turner",
            "phone": "+1234567890",
            "headline": "Senior Backend Engineer",
            "summary": "Experienced Python and Django developer",
            "location": "San Francisco, CA",
            "resume_url": "https://storage.example.com/resumes/alex.pdf",
            "linkedin_url": "https://linkedin.com/in/alexturner",
            "github_url": "https://github.com/alexturner",
            "portfolio_url": "https://alexturner.dev",
            "skills": ["Python", "Django", "PostgreSQL", "Docker"],
            "education": [{"degree": "B.S. Computer Science", "university": "Stanford"}],
            "experience": 5,
        }
        response = self.client.post(
            "/api/integration/candidates/sync/",
            data=payload,
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get("success"))
        self.assertEqual(response.data.get("human_db_user_id"), self.valid_uuid)
        self.assertEqual(response.data.get("email"), "alex.turner@example.com")

        # Verify database state
        user = User.objects.get(pk=response.data["interview_user_id"])
        self.assertEqual(user.email, "alex.turner@example.com")
        self.assertEqual(user.first_name, "Alex")
        self.assertEqual(user.last_name, "Turner")
        self.assertFalse(user.has_usable_password())  # Password must not be arbitrary

        profile = CandidateProfile.objects.get(pk=response.data["candidate_profile_id"])
        self.assertEqual(str(profile.human_db_user_id), self.valid_uuid)
        self.assertEqual(profile.phone, "+1234567890")
        self.assertIn("Python, Django", profile.skills)
        self.assertEqual(profile.experience, 5)
        self.assertEqual(profile.headline, "Senior Backend Engineer")
        self.assertEqual(profile.linkedin_url, "https://linkedin.com/in/alexturner")

        # Verify audit log was recorded
        self.assertTrue(
            IntegrationSyncLog.objects.filter(
                action=IntegrationSyncLog.ActionType.CANDIDATE_SYNC,
                human_db_user_id=self.valid_uuid,
            ).exists()
        )

    def test_repeated_candidate_sync_idempotent_no_duplicate(self):
        """Repeated sync with identical human_db_user_id updates the existing candidate without creating duplicates."""
        payload = {
            "human_db_user_id": self.valid_uuid,
            "email": "clara.oswald@example.com",
            "first_name": "Clara",
            "last_name": "Oswald",
            "phone": "+447123456789",
            "skills": ["Python"],
            "experience": 2,
        }

        # First sync
        r1 = self.client.post(
            "/api/integration/candidates/sync/",
            data=payload,
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        initial_user_id = r1.data["interview_user_id"]
        initial_profile_id = r1.data["candidate_profile_id"]

        user_count_before = User.objects.count()
        profile_count_before = CandidateProfile.objects.count()

        # Second sync with updated skills and experience
        payload["skills"] = ["Python", "Django", "FastAPI"]
        payload["experience"] = 3
        payload["first_name"] = "Clara Updated"

        r2 = self.client.post(
            "/api/integration/candidates/sync/",
            data=payload,
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["interview_user_id"], initial_user_id)
        self.assertEqual(r2.data["candidate_profile_id"], initial_profile_id)

        # No new users or profiles should have been created
        self.assertEqual(User.objects.count(), user_count_before)
        self.assertEqual(CandidateProfile.objects.count(), profile_count_before)

        # Updated values must be persisted
        updated_profile = CandidateProfile.objects.get(pk=initial_profile_id)
        self.assertEqual(updated_profile.experience, 3)
        self.assertIn("FastAPI", updated_profile.skills)
        self.assertEqual(updated_profile.user.first_name, "Clara Updated")

    def test_candidate_sync_with_existing_interview_user_by_email(self):
        """If user already registered on Interview Trainer, sync maps their human_db_user_id without password overwrite."""
        existing_user = User.objects.create_user(
            username="registered_candidate",
            email="existing.cand@example.com",
            password="mysecurepassword99",
            first_name="Existing",
            last_name="Candidate",
        )
        existing_profile = CandidateProfile.objects.create(
            user=existing_user,
            phone="111222333",
            skills="C++",
        )

        payload = {
            "human_db_user_id": self.valid_uuid,
            "email": "existing.cand@example.com",
            "skills": ["C++", "Python"],
            "phone": "999888777",
        }

        response = self.client.post(
            "/api/integration/candidates/sync/",
            data=payload,
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["interview_user_id"], existing_user.id)
        self.assertEqual(response.data["candidate_profile_id"], existing_profile.id)

        # Password must not be modified
        existing_user.refresh_from_db()
        self.assertTrue(existing_user.check_password("mysecurepassword99"))

        # Profile is updated with human_db_user_id
        existing_profile.refresh_from_db()
        self.assertEqual(str(existing_profile.human_db_user_id), self.valid_uuid)
        self.assertEqual(existing_profile.phone, "999888777")

    def test_invalid_uuid_rejected(self):
        """Sync with non-UUID value for human_db_user_id must return 400."""
        response = self.client.post(
            "/api/integration/candidates/sync/",
            data={
                "human_db_user_id": "not-a-valid-uuid-format",
                "email": "test@example.com",
            },
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("human_db_user_id", response.data)

    def test_invalid_email_rejected(self):
        """Sync with invalid email format must return 400."""
        response = self.client.post(
            "/api/integration/candidates/sync/",
            data={
                "human_db_user_id": self.valid_uuid,
                "email": "not-an-email",
            },
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    # -------------------------------------------------------------------------
    # Assessment Creation Tests
    # -------------------------------------------------------------------------
    def test_assessment_creation_for_synchronized_candidate_success(self):
        """Creating an assessment for a synchronized candidate succeeds with token and ID."""
        # First sync candidate
        self.client.post(
            "/api/integration/candidates/sync/",
            data={"human_db_user_id": self.valid_uuid, "email": "test.cand@example.com"},
            format="json",
            **self.auth_headers,
        )

        now = timezone.now()
        start_time = now + timedelta(hours=1)
        expire_time = now + timedelta(days=2)

        assessment_payload = {
            "human_db_user_id": self.valid_uuid,
            "title": "Full Stack Python Assessment",
            "start_time": start_time.isoformat(),
            "expire_time": expire_time.isoformat(),
            "duration_minutes": 60,
            "has_coding": True,
        }

        response = self.client.post(
            "/api/integration/assessments/",
            data=assessment_payload,
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data.get("success"))
        self.assertIn("assessment_id", response.data)
        self.assertIn("token", response.data)
        self.assertEqual(
            response.data.get("candidate", {}).get("human_db_user_id"),
            self.valid_uuid,
        )

        assessment_id = response.data["assessment_id"]
        assessment = Assessment.objects.get(pk=assessment_id)
        self.assertEqual(assessment.title, "Full Stack Python Assessment")
        self.assertEqual(assessment.status, Assessment.Status.PENDING)
        self.assertEqual(assessment.candidate_status, Assessment.CandidateStatus.NOT_STARTED)
        self.assertTrue(assessment.has_coding)
        self.assertTrue(assessment.token)

        # Verify question assignment mechanics
        self.assertGreater(assessment.questions.count(), 0)
        self.assertGreater(assessment.coding_questions.count(), 0)

        # Verify audit log
        self.assertTrue(
            IntegrationSyncLog.objects.filter(
                action=IntegrationSyncLog.ActionType.ASSESSMENT_CREATE,
                assessment_id=assessment_id,
            ).exists()
        )

    def test_assessment_creation_unknown_human_db_user_id_rejected(self):
        """Creating an assessment for an unsynchronized human_db_user_id returns 404."""
        now = timezone.now()
        unknown_uuid = str(uuid.uuid4())
        response = self.client.post(
            "/api/integration/assessments/",
            data={
                "human_db_user_id": unknown_uuid,
                "title": "Python Test",
                "start_time": (now + timedelta(hours=1)).isoformat(),
                "expire_time": (now + timedelta(days=1)).isoformat(),
                "duration_minutes": 30,
            },
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_assessment_creation_invalid_expire_time_rejected(self):
        """Assessment with expire_time <= start_time must be rejected with 400 validation error."""
        self.client.post(
            "/api/integration/candidates/sync/",
            data={"human_db_user_id": self.valid_uuid, "email": "expire.test@example.com"},
            format="json",
            **self.auth_headers,
        )

        now = timezone.now()
        response = self.client.post(
            "/api/integration/assessments/",
            data={
                "human_db_user_id": self.valid_uuid,
                "title": "Invalid Times Test",
                "start_time": (now + timedelta(days=2)).isoformat(),
                "expire_time": (now + timedelta(days=1)).isoformat(),  # Earlier than start
                "duration_minutes": 30,
            },
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expire_time", response.data)

    # -------------------------------------------------------------------------
    # Assessment Retrieval Tests
    # -------------------------------------------------------------------------
    def test_assessment_retrieval_success(self):
        """GET /api/integration/assessments/<id>/ returns comprehensive assessment details."""
        # Sync candidate and create assessment
        sync_resp = self.client.post(
            "/api/integration/candidates/sync/",
            data={"human_db_user_id": self.valid_uuid, "email": "retrieve.cand@example.com"},
            format="json",
            **self.auth_headers,
        )
        cand_user = User.objects.get(pk=sync_resp.data["interview_user_id"])

        employer_user = User.objects.create_user(username="test_emp", email="emp@test.com")
        EmployerProfile.objects.create(user=employer_user, company="Test Corp")

        now = timezone.now()
        assessment = Assessment.objects.create(
            employer=employer_user,
            candidate=cand_user,
            title="Backend Architect Assessment",
            start_time=now,
            expire_time=now + timedelta(days=2),
            duration_minutes=45,
            has_coding=False,
            status=Assessment.Status.PENDING,
            candidate_status=Assessment.CandidateStatus.NOT_STARTED,
        )

        response = self.client.get(
            f"/api/integration/assessments/{assessment.id}/",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["assessment_id"], assessment.id)
        self.assertEqual(response.data["human_db_user_id"], self.valid_uuid)
        self.assertEqual(response.data["title"], "Backend Architect Assessment")
        self.assertEqual(response.data["status"], "PENDING")
        self.assertEqual(response.data["candidate_status"], "NOT_STARTED")
        self.assertEqual(response.data["duration_minutes"], 45)
        self.assertFalse(response.data["has_coding"])
        self.assertEqual(response.data["token"], assessment.token)

    def test_assessment_retrieval_not_found(self):
        """GET for nonexistent assessment ID returns 404."""
        response = self.client.get(
            "/api/integration/assessments/9999999/",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -------------------------------------------------------------------------
    # Result Retrieval Tests
    # -------------------------------------------------------------------------
    def test_result_retrieval_when_result_exists(self):
        """GET /api/integration/results/<id>/ returns complete result metrics when assessment has completed."""
        sync_resp = self.client.post(
            "/api/integration/candidates/sync/",
            data={"human_db_user_id": self.valid_uuid, "email": "result.cand@example.com"},
            format="json",
            **self.auth_headers,
        )
        cand_user = User.objects.get(pk=sync_resp.data["interview_user_id"])

        employer_user = User.objects.create_user(username="emp_result", email="emp_res@test.com")
        EmployerProfile.objects.create(user=employer_user, company="Result Corp")

        now = timezone.now()
        assessment = Assessment.objects.create(
            employer=employer_user,
            candidate=cand_user,
            title="Data Science Assessment",
            start_time=now,
            expire_time=now + timedelta(days=1),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.COMPLETED,
            candidate_status=Assessment.CandidateStatus.ATTENDED,
        )

        Result.objects.create(
            assessment=assessment,
            logical_correct=4,
            logical_total=5,
            quant_correct=5,
            quant_total=5,
            technical_correct=4,
            technical_total=5,
            total_correct=13,
            total_questions=15,
            percentage=86.67,
            has_coding=True,
            aptitude_score=86.67,
            coding_score=90.00,
            overall_score=88.34,
            violation_count=0,
            auto_submitted_for_malpractice=False,
            submission_reason="Standard candidate completion",
            completed_at=now,
        )

        response = self.client.get(
            f"/api/integration/results/{assessment.id}/",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["assessment_id"], assessment.id)
        self.assertEqual(response.data["human_db_user_id"], self.valid_uuid)
        self.assertEqual(response.data["total_correct"], 13)
        self.assertEqual(response.data["total_questions"], 15)
        self.assertAlmostEqual(response.data["percentage"], 86.67, places=2)
        self.assertAlmostEqual(response.data["overall_score"], 88.34, places=2)
        self.assertTrue(response.data["passed"])
        self.assertFalse(response.data["auto_submitted_for_malpractice"])
        self.assertEqual(response.data["submission_reason"], "Standard candidate completion")

    def test_result_retrieval_when_result_does_not_exist(self):
        """GET /api/integration/results/<id>/ returns 404 when assessment exists but no result has been recorded."""
        sync_resp = self.client.post(
            "/api/integration/candidates/sync/",
            data={"human_db_user_id": self.valid_uuid, "email": "pending.cand@example.com"},
            format="json",
            **self.auth_headers,
        )
        cand_user = User.objects.get(pk=sync_resp.data["interview_user_id"])

        employer_user = User.objects.create_user(username="emp_pending", email="emp_p@test.com")
        EmployerProfile.objects.create(user=employer_user, company="Pending Corp")

        now = timezone.now()
        assessment = Assessment.objects.create(
            employer=employer_user,
            candidate=cand_user,
            title="Pending Assessment",
            start_time=now,
            expire_time=now + timedelta(days=1),
            duration_minutes=30,
            status=Assessment.Status.PENDING,
        )

        response = self.client.get(
            f"/api/integration/results/{assessment.id}/",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    # -------------------------------------------------------------------------
    # Result Callback Tests
    # -------------------------------------------------------------------------
    def test_result_callback_accepted_and_logged(self):
        """POST /api/integration/results/callback/ validates payload and logs callback without error."""
        callback_payload = {
            "assessment_id": 42,
            "human_db_user_id": self.valid_uuid,
            "overall_score": 92.5,
            "passed": True,
            "submission_reason": "Automated evaluation test",
        }
        response = self.client.post(
            "/api/integration/results/callback/",
            data=callback_payload,
            format="json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get("success"))

        self.assertTrue(
            IntegrationSyncLog.objects.filter(
                action=IntegrationSyncLog.ActionType.RESULT_CALLBACK,
                assessment_id=42,
            ).exists()
        )
