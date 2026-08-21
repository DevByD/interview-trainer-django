"""Phase 3 automated tests for security, file validation, error handlers, and cron endpoint."""

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.conf import settings

from accounts.models import CandidateProfile
from assessments.models import Assessment


class Phase3SecurityAndReadinessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.cand_user = User.objects.create_user(
            username="sec_cand@test.com",
            email="sec_cand@test.com",
            password="Password123!",
            first_name="SecurityCandidate",
        )
        self.cand_profile = CandidateProfile.objects.create(user=self.cand_user)

    def test_resume_valid_pdf_accepted(self):
        self.client.login(username="sec_cand@test.com", password="Password123!")
        pdf_file = SimpleUploadedFile(
            "my_resume.pdf",
            b"%PDF-1.4 sample resume content",
            content_type="application/pdf",
        )
        res = self.client.post(
            reverse("candidates:candidate_profile"),
            data={
                "name": "Security Candidate",
                "phone": "+1234567890",
                "education": "B.S. in Cybersecurity",
                "skills": "Network Security, Python",
                "experience": 2,
                "resume": pdf_file,
            },
        )
        self.assertEqual(res.status_code, 302)
        self.cand_profile.refresh_from_db()
        self.assertTrue(bool(self.cand_profile.resume))
        self.assertTrue(self.cand_profile.resume.name.endswith(".pdf"))

    def test_resume_executable_rejected(self):
        self.client.login(username="sec_cand@test.com", password="Password123!")
        exe_file = SimpleUploadedFile(
            "malware.exe",
            b"MZ executable binary payload",
            content_type="application/x-msdownload",
        )
        res = self.client.post(
            reverse("candidates:candidate_profile"),
            data={
                "name": "Security Candidate",
                "phone": "+1234567890",
                "education": "B.S. in Cybersecurity",
                "skills": "Security",
                "experience": 2,
                "resume": exe_file,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Executable and script files are strictly prohibited")

    def test_resume_oversized_rejected(self):
        self.client.login(username="sec_cand@test.com", password="Password123!")
        # 6MB dummy content (> 5MB limit)
        oversized_content = b"0" * (6 * 1024 * 1024)
        big_file = SimpleUploadedFile(
            "huge_resume.pdf",
            oversized_content,
            content_type="application/pdf",
        )
        res = self.client.post(
            reverse("candidates:candidate_profile"),
            data={
                "name": "Security Candidate",
                "phone": "+1234567890",
                "education": "B.S. in Cybersecurity",
                "skills": "Security",
                "experience": 2,
                "resume": big_file,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Resume file size cannot exceed 5MB")

    def test_cron_endpoint_unauthorized_without_token(self):
        res = self.client.get(reverse("assessments:cron_expire_assessments"))
        self.assertEqual(res.status_code, 403)
        self.assertJSONEqual(
            res.content,
            {"error": "unauthorized", "message": "Invalid or missing cron authorization key."},
        )

    def test_cron_endpoint_authorized_with_token(self):
        cron_secret = getattr(settings, "CRON_SECRET_KEY", "dev-cron-secret-key-12345")
        res = self.client.get(
            reverse("assessments:cron_expire_assessments"),
            headers={"Authorization": f"Bearer {cron_secret}"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("status", res.json())
        self.assertEqual(res.json()["status"], "success")

    def test_404_error_page_rendered(self):
        res = self.client.get("/non-existent-page-url-xyz/")
        self.assertEqual(res.status_code, 404)
        self.assertContains(res, "404 — Page Not Found", status_code=404)
