import csv
import io
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CandidateProfile, EmployerProfile
from assessments.models import (
    Assessment,
    AssessmentCodingQuestion,
    AssessmentQuestion,
    CodingQuestion,
    CodingSubmission,
    CodingTestCase,
    Question,
)
from results.models import Result

User = get_user_model()


class EmployerReportingAndCsvExportTests(TestCase):
    """Tests for employer evaluation reports, multi-tenant security, charts, and CSV exports."""

    def setUp(self):
        self.now = timezone.now()

        # Employer 1
        self.emp1 = User.objects.create_user(
            username="emp1@test.com",
            email="emp1@test.com",
            password="Password123!",
            first_name="Employer",
            last_name="One",
        )
        EmployerProfile.objects.create(user=self.emp1, company="Acme Corp")

        # Employer 2 (different tenant)
        self.emp2 = User.objects.create_user(
            username="emp2@test.com",
            email="emp2@test.com",
            password="Password123!",
            first_name="Employer",
            last_name="Two",
        )
        EmployerProfile.objects.create(user=self.emp2, company="Beta Corp")

        # Candidate
        self.cand = User.objects.create_user(
            username="cand1@test.com",
            email="cand1@test.com",
            password="Password123!",
            first_name="Candidate",
            last_name="One",
        )
        CandidateProfile.objects.create(user=self.cand, phone="1234567890", education="B.Tech")


        # Create Questions
        self.q1 = Question.objects.create(
            section=Question.Sections.LOGICAL,
            question_text="Logical Q1",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_answer="A",
        )
        self.q2 = Question.objects.create(
            section=Question.Sections.QUANTITATIVE,
            question_text="Quant Q1",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_answer="B",
        )
        self.q3 = Question.objects.create(
            section=Question.Sections.TECHNICAL,
            question_text="Tech Q1",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            correct_answer="C",
        )


        # Create Coding Question
        self.cq1 = CodingQuestion.objects.create(
            title="Reverse String",
            slug="reverse-string",
            description="Reverse the input string",
            difficulty=Question.Difficulties.EASY,
            category=CodingQuestion.Categories.STRINGS,
            input_format="String s",
            output_format="String",
            sample_input="hello",
            sample_output="olleh",
        )

        CodingTestCase.objects.create(
            question=self.cq1,
            order=1,
            input_data="hello",
            expected_output="olleh",
            is_sample=True,
        )
        CodingTestCase.objects.create(
            question=self.cq1,
            order=2,
            input_data="world",
            expected_output="dlrow",
            is_sample=False,
        )


        # Create Assessment for Employer 1
        self.assessment1 = Assessment.objects.create(
            employer=self.emp1,
            candidate=self.cand,
            title="Software Engineering Assessment",
            start_time=self.now - timedelta(minutes=25),
            expire_time=self.now + timedelta(days=1),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.COMPLETED,
            violation_count=1,
            max_violations=3,
            last_violation_type="FULLSCREEN_EXIT",
            last_violation_at=self.now - timedelta(minutes=15),
            auto_submitted_for_malpractice=False,
            submission_reason="Standard candidate completion",
        )
        AssessmentQuestion.objects.create(assessment=self.assessment1, question=self.q1, order=1)
        AssessmentQuestion.objects.create(assessment=self.assessment1, question=self.q2, order=2)
        AssessmentQuestion.objects.create(assessment=self.assessment1, question=self.q3, order=3)
        AssessmentCodingQuestion.objects.create(assessment=self.assessment1, question=self.cq1, order=1)

        CodingSubmission.objects.create(
            assessment=self.assessment1,
            question=self.cq1,
            language="python",
            source_code="def solve(s): return s[::-1]",
            passed_test_cases=2,
            total_test_cases=2,
            score=Decimal("100.00"),
        )

        self.result1 = Result.objects.create(
            assessment=self.assessment1,
            logical_correct=1,
            logical_total=1,
            quant_correct=1,
            quant_total=1,
            technical_correct=1,
            technical_total=1,
            total_correct=3,
            total_questions=3,
            percentage=Decimal("100.00"),
            has_coding=True,
            aptitude_score=Decimal("100.00"),
            coding_score=Decimal("100.00"),
            overall_score=Decimal("100.00"),
            violation_count=1,
            auto_submitted_for_malpractice=False,
            submission_reason="Standard candidate completion",
            completed_at=self.now - timedelta(minutes=5),
        )

    def test_01_employer_can_view_evaluation_report_with_all_metrics(self):
        """Verify Employer 1 can view the candidate evaluation report with metrics, charts, and proctoring log."""
        self.client.login(username="emp1@test.com", password="Password123!")
        url = reverse("results:employer_result", kwargs={"result_id": self.result1.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        # Verify page components
        self.assertContains(res, "Candidate Evaluation Report")
        self.assertContains(res, "Software Engineering Assessment")
        self.assertContains(res, "Candidate One")
        self.assertContains(res, "cand1@test.com")
        self.assertContains(res, "Aptitude Performance Breakdown")
        self.assertContains(res, "Coding Evaluation Breakdown")
        self.assertContains(res, "Reverse String")
        self.assertContains(res, "Proctoring &amp; Integrity Record")
        self.assertContains(res, "Violations: 1 / 3")
        self.assertContains(res, "FULLSCREEN_EXIT")
        self.assertContains(res, "Export Results (CSV)")

    def test_02_multi_tenant_security_employer2_cannot_view_employer1_result(self):
        """Verify Employer 2 receives 403 Forbidden when attempting to view Employer 1's candidate result."""
        self.client.login(username="emp2@test.com", password="Password123!")
        url = reverse("results:employer_result", kwargs={"result_id": self.result1.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 403)

    def test_03_candidate_cannot_access_employer_result_view(self):
        """Verify candidate cannot access the employer evaluation endpoint (redirected / blocked)."""
        self.client.login(username="cand1@test.com", password="Password123!")
        url = reverse("results:employer_result", kwargs={"result_id": self.result1.id})
        res = self.client.get(url)
        # @employer_required redirects candidate with a warning or permission denied
        self.assertIn(res.status_code, [302, 403])

    def test_04_employer_single_result_csv_export(self):
        """Verify Employer 1 can export assessment result as CSV with exact required columns and zero leaked secrets."""
        self.client.login(username="emp1@test.com", password="Password123!")
        url = reverse("results:employer_result_csv_export", kwargs={"result_id": self.result1.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn("attachment; filename=", res["Content-Disposition"])

        content = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Verify Header row
        expected_header = [
            "Candidate Name",
            "Email",
            "Status",
            "Aptitude Score",
            "Coding Score",
            "Overall Score",
            "Violations",
            "Auto Submitted",
            "Submission Reason",
            "Completed At",
        ]
        self.assertEqual(rows[0], expected_header)

        # Verify Data row
        data_row = rows[1]
        self.assertEqual(data_row[0], "Candidate One")
        self.assertEqual(data_row[1], "cand1@test.com")
        self.assertEqual(data_row[2], "Completed")
        self.assertEqual(data_row[3], "100.00%")
        self.assertEqual(data_row[4], "100.00%")
        self.assertEqual(data_row[5], "100.00%")
        self.assertEqual(data_row[6], "1/3")
        self.assertEqual(data_row[7], "No")
        self.assertEqual(data_row[8], "Standard candidate completion")

        # Verify No secrets/tokens/passwords in CSV
        self.assertNotIn("Password123!", content)
        self.assertNotIn(self.assessment1.token, content)

    def test_05_multi_tenant_security_employer2_cannot_export_employer1_csv(self):
        """Verify Employer 2 receives 403 Forbidden when attempting to export Employer 1's candidate CSV."""
        self.client.login(username="emp2@test.com", password="Password123!")
        url = reverse("results:employer_result_csv_export", kwargs={"result_id": self.result1.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 403)

    def test_06_employer_all_results_csv_export(self):
        """Verify employer can export all their candidate evaluations in a single CSV report."""
        self.client.login(username="emp1@test.com", password="Password123!")
        url = reverse("results:employer_all_results_csv_export")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")

        content = res.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "Candidate One")
        self.assertEqual(rows[1][1], "cand1@test.com")
        self.assertEqual(rows[1][2], "Software Engineering Assessment")
