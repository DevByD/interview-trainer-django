"""Comprehensive Phase 2 Automated Tests for Assessment Engine."""

from datetime import timedelta
import secrets
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CandidateProfile, EmployerProfile
from assessments.models import Answer, Assessment, AssessmentQuestion, Question
from assessments.services import expire_past_due_assessments, grade_and_complete_assessment
from results.models import Result


class Phase2AssessmentEngineTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

        # Seed Question Bank
        self.logical_q1 = Question.objects.create(
            section=Question.Sections.LOGICAL,
            question_text="What comes next: 2, 4, 6, 8, ?",
            option_a="10", option_b="12", option_c="14", option_d="16",
            correct_answer="A", difficulty=Question.Difficulties.EASY,
        )
        self.logical_q2 = Question.objects.create(
            section=Question.Sections.LOGICAL,
            question_text="Find the odd one out: Apple, Banana, Carrot, Orange",
            option_a="Apple", option_b="Banana", option_c="Carrot", option_d="Orange",
            correct_answer="C", difficulty=Question.Difficulties.EASY,
        )
        self.quant_q1 = Question.objects.create(
            section=Question.Sections.QUANTITATIVE,
            question_text="What is 15% of 200?",
            option_a="20", option_b="30", option_c="40", option_d="25",
            correct_answer="B", difficulty=Question.Difficulties.EASY,
        )
        self.tech_q1 = Question.objects.create(
            section=Question.Sections.TECHNICAL,
            question_text="Which data structure operates on LIFO?",
            option_a="Queue", option_b="Stack", option_c="Tree", option_d="Graph",
            correct_answer="B", difficulty=Question.Difficulties.EASY,
        )

        # Employer 1
        self.emp_user1 = User.objects.create_user(
            username="emp1@techcorp.com", email="emp1@techcorp.com", password="Password123!", first_name="EmpOne"
        )
        self.emp_prof1 = EmployerProfile.objects.create(user=self.emp_user1, company="TechCorp")

        # Employer 2
        self.emp_user2 = User.objects.create_user(
            username="emp2@globalhire.com", email="emp2@globalhire.com", password="Password123!", first_name="EmpTwo"
        )
        self.emp_prof2 = EmployerProfile.objects.create(user=self.emp_user2, company="GlobalHire")

        # Candidate 1
        self.cand_user1 = User.objects.create_user(
            username="cand1@test.com", email="cand1@test.com", password="Password123!", first_name="Alice"
        )
        self.cand_prof1 = CandidateProfile.objects.create(
            user=self.cand_user1, phone="1234567890", education="B.S.", skills="Python, Django"
        )

        # Candidate 2
        self.cand_user2 = User.objects.create_user(
            username="cand2@test.com", email="cand2@test.com", password="Password123!", first_name="Bob"
        )
        self.cand_prof2 = CandidateProfile.objects.create(
            user=self.cand_user2, phone="0987654321", education="M.S.", skills="SQL, React"
        )

    # 1. Employer creates assessment
    def test_01_employer_creates_assessment(self):
        self.client.login(username="emp1@techcorp.com", password="Password123!")
        post_data = {
            "candidate": self.cand_user1.id,
            "title": "Backend Engineering Test",
            "sections": ["LOGICAL", "QUANTITATIVE", "TECHNICAL"],
            "logical_count": 2,
            "quant_count": 1,
            "technical_count": 1,
            "start_date": self.now.date().isoformat(),
            "start_time": (self.now - timedelta(minutes=5)).strftime("%H:%M"),
            "expire_date": (self.now + timedelta(days=1)).date().isoformat(),
            "expire_time": (self.now + timedelta(days=1)).strftime("%H:%M"),
            "duration_minutes": 30,
        }
        res = self.client.post(reverse("assessments:employer_assessment_create"), data=post_data)
        self.assertEqual(res.status_code, 302)

        assessment = Assessment.objects.filter(employer=self.emp_user1, candidate=self.cand_user1).first()
        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.title, "Backend Engineering Test")
        self.assertEqual(assessment.duration_minutes, 30)
        self.assertEqual(assessment.questions.count(), 4)

    # 2. Employer can assign only registered candidates
    def test_02_assign_only_registered_candidates(self):
        # Create non-candidate user (e.g. staff or employer without candidate_profile)
        other_user = User.objects.create_user(username="noncand@test.com", email="noncand@test.com", password="Password123!")
        self.client.login(username="emp1@techcorp.com", password="Password123!")
        post_data = {
            "candidate": other_user.id,
            "title": "Invalid Test",
            "sections": ["LOGICAL"],
            "logical_count": 1,
            "start_date": self.now.date().isoformat(),
            "start_time": "10:00",
            "expire_date": (self.now + timedelta(days=1)).date().isoformat(),
            "expire_time": "10:00",
            "duration_minutes": 30,
        }
        res = self.client.post(reverse("assessments:employer_assessment_create"), data=post_data)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Assessment.objects.filter(title="Invalid Test").exists())

    # 3. Secure token is generated & 4. Token is unique
    def test_03_and_04_secure_token_generated_and_unique(self):
        a1 = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Test 1",
            start_time=self.now, expire_time=self.now + timedelta(hours=2), duration_minutes=30
        )
        a2 = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user2, title="Test 2",
            start_time=self.now, expire_time=self.now + timedelta(hours=2), duration_minutes=30
        )
        self.assertTrue(len(a1.token) >= 32)
        self.assertTrue(len(a2.token) >= 32)
        self.assertNotEqual(a1.token, a2.token)
        self.assertNotEqual(a1.token, str(a1.id))

    # 5. Candidate can access own assessment
    def test_05_candidate_can_access_own_assessment(self):
        assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Alice Test",
            start_time=self.now - timedelta(minutes=10), expire_time=self.now + timedelta(hours=2), duration_minutes=30
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.logical_q1, order=1)
        self.client.login(username="cand1@test.com", password="Password123!")

        res = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Alice Test")
        self.assertContains(res, "START ASSESSMENT")

    # 6. Candidate cannot access another candidate's assessment
    def test_06_candidate_cannot_access_another_assessment(self):
        assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user2, title="Bob Test",
            start_time=self.now - timedelta(minutes=10), expire_time=self.now + timedelta(hours=2), duration_minutes=30
        )
        self.client.login(username="cand1@test.com", password="Password123!")
        res = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
        self.assertEqual(res.status_code, 403)

    # 7. Candidate cannot start before start time
    def test_07_candidate_cannot_start_before_start_time(self):
        future_assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Future Test",
            start_time=self.now + timedelta(days=2), expire_time=self.now + timedelta(days=3), duration_minutes=30
        )
        self.client.login(username="cand1@test.com", password="Password123!")
        res = self.client.get(reverse("assessments:test_entry", kwargs={"token": future_assessment.token}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Assessment Not Yet Open")

    # 8. Candidate can start during valid window
    def test_08_candidate_can_start_during_valid_window(self):
        assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Active Test",
            start_time=self.now - timedelta(minutes=5), expire_time=self.now + timedelta(hours=1), duration_minutes=30
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.logical_q1, order=1)
        self.client.login(username="cand1@test.com", password="Password123!")

        res = self.client.post(reverse("assessments:test_start", kwargs={"token": assessment.token}))
        self.assertEqual(res.status_code, 302)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.ONGOING)

    # 9. Questions are displayed & 10. Correct answers are not exposed
    def test_09_and_10_questions_displayed_correct_answers_not_exposed(self):
        assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Active Test",
            start_time=self.now - timedelta(minutes=5), expire_time=self.now + timedelta(hours=1),
            duration_minutes=30, status=Assessment.Status.ONGOING
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.logical_q1, order=1)
        self.client.login(username="cand1@test.com", password="Password123!")

        res = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "What comes next: 2, 4, 6, 8, ?")
        # Ensure correct answer 'A' is not rendered in data attributes or hidden inputs as the answer key
        self.assertNotContains(res, 'correct_answer')
        self.assertNotContains(res, 'data-correct')

    # 11. Answers are saved & 12. Invalid answers are rejected
    def test_11_and_12_answers_saved_and_invalid_rejected(self):
        assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Active Test",
            start_time=self.now - timedelta(minutes=5), expire_time=self.now + timedelta(hours=1),
            duration_minutes=30, status=Assessment.Status.ONGOING
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.logical_q1, order=1)
        self.client.login(username="cand1@test.com", password="Password123!")

        # Valid answer save via AJAX
        res_valid = self.client.post(
            reverse("assessments:test_save_answer", kwargs={"token": assessment.token}),
            data={"question_id": self.logical_q1.id, "selected_option": "A"},
            content_type="application/json"
        )
        self.assertEqual(res_valid.status_code, 200)
        self.assertTrue(Answer.objects.filter(assessment=assessment, question=self.logical_q1, selected_answer="A").exists())

        # Invalid answer choice 'X'
        res_inv = self.client.post(
            reverse("assessments:test_save_answer", kwargs={"token": assessment.token}),
            data={"question_id": self.logical_q1.id, "selected_option": "X"},
            content_type="application/json"
        )
        self.assertEqual(res_inv.status_code, 400)

    # 13. Candidate can submit & 14. Duplicate submission is rejected
    def test_13_and_14_submission_and_duplicate_rejected(self):
        assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Active Test",
            start_time=self.now - timedelta(minutes=5), expire_time=self.now + timedelta(hours=1),
            duration_minutes=30, status=Assessment.Status.ONGOING
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.logical_q1, order=1)
        self.client.login(username="cand1@test.com", password="Password123!")

        submit_res = self.client.post(
            reverse("assessments:test_submit", kwargs={"token": assessment.token}),
            data={f"q_{self.logical_q1.id}": "A"}
        )
        self.assertEqual(submit_res.status_code, 302)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.COMPLETED)
        self.assertEqual(assessment.candidate_status, Assessment.CandidateStatus.ATTENDED)
        self.assertTrue(hasattr(assessment, "result"))

        # Duplicate submit attempt redirects gracefully to result without re-grading
        dup_res = self.client.post(
            reverse("assessments:test_submit", kwargs={"token": assessment.token}),
            data={f"q_{self.logical_q1.id}": "B"}
        )
        self.assertEqual(dup_res.status_code, 302)
        # Score unchanged
        self.assertEqual(assessment.result.percentage, Decimal("100.00"))

    # 15. Late submission is rejected
    def test_15_late_submission_is_rejected(self):
        past_assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Late Test",
            start_time=self.now - timedelta(hours=3), expire_time=self.now - timedelta(hours=1),
            duration_minutes=30, status=Assessment.Status.ONGOING
        )
        AssessmentQuestion.objects.create(assessment=past_assessment, question=self.logical_q1, order=1)
        self.client.login(username="cand1@test.com", password="Password123!")

        res = self.client.post(
            reverse("assessments:test_submit", kwargs={"token": past_assessment.token}),
            data={f"q_{self.logical_q1.id}": "A"}
        )
        self.assertEqual(res.status_code, 302)
        past_assessment.refresh_from_db()
        self.assertEqual(past_assessment.status, Assessment.Status.EXPIRED)
        self.assertEqual(past_assessment.candidate_status, Assessment.CandidateStatus.NOT_ATTENDED)
        self.assertFalse(hasattr(past_assessment, "result"))

    # 16-21. Auto grading, section scores, percentage, Result record creation
    def test_16_to_21_auto_grading_scores_and_result(self):
        assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Full Assessment",
            start_time=self.now - timedelta(minutes=5), expire_time=self.now + timedelta(hours=1),
            duration_minutes=30, status=Assessment.Status.ONGOING
        )
        # 2 Logical, 1 Quant, 1 Tech = 4 total questions
        AssessmentQuestion.objects.create(assessment=assessment, question=self.logical_q1, order=1) # Correct: A
        AssessmentQuestion.objects.create(assessment=assessment, question=self.logical_q2, order=2) # Correct: C
        AssessmentQuestion.objects.create(assessment=assessment, question=self.quant_q1, order=3)   # Correct: B
        AssessmentQuestion.objects.create(assessment=assessment, question=self.tech_q1, order=4)    # Correct: B

        # Candidate answers:
        # q1: A (Correct)
        # q2: A (Incorrect, correct is C)
        # q3: B (Correct)
        # q4: B (Correct)
        # Result should be: 3/4 = 75.00%
        # Logical: 1/2
        # Quant: 1/1
        # Tech: 1/1
        answers = {
            self.logical_q1.id: "A",
            self.logical_q2.id: "A",
            self.quant_q1.id: "B",
            self.tech_q1.id: "B",
        }
        result = grade_and_complete_assessment(assessment, answers)

        self.assertEqual(result.total_correct, 3)
        self.assertEqual(result.total_questions, 4)
        self.assertEqual(result.percentage, Decimal("75.00"))
        self.assertEqual(result.logical_correct, 1)
        self.assertEqual(result.logical_total, 2)
        self.assertEqual(result.quant_correct, 1)
        self.assertEqual(result.quant_total, 1)
        self.assertEqual(result.technical_correct, 1)
        self.assertEqual(result.technical_total, 1)
        self.assertTrue(result.passed)

    # 22. Candidate can see own result & 23. Candidate cannot see another result
    def test_22_and_23_candidate_result_access(self):
        assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Graded Test",
            start_time=self.now - timedelta(hours=1), expire_time=self.now + timedelta(hours=1),
            duration_minutes=30, status=Assessment.Status.COMPLETED, candidate_status=Assessment.CandidateStatus.ATTENDED
        )
        result = Result.objects.create(
            assessment=assessment, total_correct=3, total_questions=4, percentage=Decimal("75.00"),
            logical_correct=1, logical_total=2, quant_correct=1, quant_total=1, technical_correct=1, technical_total=1
        )

        # Alice accesses own result
        self.client.login(username="cand1@test.com", password="Password123!")
        res = self.client.get(reverse("results:candidate_result", kwargs={"result_id": result.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "75.00%")
        self.assertContains(res, "Graded Test")

        # Bob tries to access Alice's result
        self.client.login(username="cand2@test.com", password="Password123!")
        res_bob = self.client.get(reverse("results:candidate_result", kwargs={"result_id": result.id}))
        self.assertEqual(res_bob.status_code, 403)

    # 24. Employer can see own assessment result & 25. Employer cannot see another employer's result
    def test_24_and_25_employer_result_access(self):
        assessment = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Employer Evaluation Test",
            start_time=self.now - timedelta(hours=1), expire_time=self.now + timedelta(hours=1),
            duration_minutes=30, status=Assessment.Status.COMPLETED, candidate_status=Assessment.CandidateStatus.ATTENDED
        )
        result = Result.objects.create(
            assessment=assessment, total_correct=4, total_questions=4, percentage=Decimal("100.00"),
            logical_correct=2, logical_total=2, quant_correct=1, quant_total=1, technical_correct=1, technical_total=1
        )

        # Employer 1 accesses result
        self.client.login(username="emp1@techcorp.com", password="Password123!")
        res = self.client.get(reverse("results:employer_result", kwargs={"result_id": result.id}))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "100.00%")
        self.assertContains(res, "Alice")

        # Employer 2 tries to access Employer 1's result
        self.client.login(username="emp2@globalhire.com", password="Password123!")
        res_emp2 = self.client.get(reverse("results:employer_result", kwargs={"result_id": result.id}))
        self.assertEqual(res_emp2.status_code, 403)

    # 26. Expiry command works, 27. Becomes EXPIRED, 28. NOT_ATTENDED, 29. Cannot be started, 30. COMPLETED not expired
    def test_26_to_30_expiry_command_and_missed_test_rules(self):
        # 1. Past due pending assessment
        past_pending = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user1, title="Past Pending",
            start_time=self.now - timedelta(days=2), expire_time=self.now - timedelta(days=1),
            duration_minutes=30, status=Assessment.Status.PENDING, candidate_status=Assessment.CandidateStatus.NOT_STARTED
        )
        # 2. Completed past due assessment
        past_completed = Assessment.objects.create(
            employer=self.emp_user1, candidate=self.cand_user2, title="Past Completed",
            start_time=self.now - timedelta(days=2), expire_time=self.now - timedelta(days=1),
            duration_minutes=30, status=Assessment.Status.COMPLETED, candidate_status=Assessment.CandidateStatus.ATTENDED
        )

        # Run expiry command
        call_command("expire_assessments")

        past_pending.refresh_from_db()
        past_completed.refresh_from_db()

        # Rule 27 & 28: Past pending becomes EXPIRED and NOT_ATTENDED
        self.assertEqual(past_pending.status, Assessment.Status.EXPIRED)
        self.assertEqual(past_pending.candidate_status, Assessment.CandidateStatus.NOT_ATTENDED)

        # Rule 30: Completed assessment remains COMPLETED
        self.assertEqual(past_completed.status, Assessment.Status.COMPLETED)
        self.assertEqual(past_completed.candidate_status, Assessment.CandidateStatus.ATTENDED)

        # Rule 29: Expired assessment cannot be started
        self.client.login(username="cand1@test.com", password="Password123!")
        res_gate = self.client.get(reverse("assessments:test_entry", kwargs={"token": past_pending.token}))
        self.assertEqual(res_gate.status_code, 200)
        self.assertContains(res_gate, "Assessment Expired (MISSED TEST)")
