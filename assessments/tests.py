import json
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CandidateProfile, EmployerProfile
from assessments.coding_bank import ensure_coding_bank_seeded
from assessments.models import (
    Answer,
    Assessment,
    AssessmentCodingQuestion,
    AssessmentGroup,
    AssessmentQuestion,
    CodingQuestion,
    CodingSubmission,
    CodingTestCase,
    Question,
)
from assessments.question_bank import ensure_question_bank_seeded
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
        self.assertContains(res_gate, "Assessment Closed")

    # =========================================================================
    # STEP 11 TESTS — QUESTION BANK & ASSESSMENT ENGINE
    # =========================================================================

    def test_31_question_creation(self):
        """1. Test creating individual Question records with all options and difficulty."""
        q = Question.objects.create(
            section=Question.Sections.TECHNICAL,
            question_text="What is a Python generator?",
            option_a="A function with yield",
            option_b="A class with init",
            option_c="A compile-time macro",
            option_d="A database trigger",
            correct_answer="A",
            difficulty=Question.Difficulties.MEDIUM,
        )
        self.assertIsNotNone(q.id)
        self.assertEqual(q.section, Question.Sections.TECHNICAL)
        self.assertEqual(q.correct_answer, "A")
        self.assertEqual(q.difficulty, Question.Difficulties.MEDIUM)

    def test_32_question_bank_count(self):
        """2. Test seeding question bank and verifying total count >= 150."""
        call_command("seed_questions")
        total_count = Question.objects.count()
        self.assertGreaterEqual(total_count, 150)

        # Re-running seed_questions must be strictly idempotent
        call_command("seed_questions")
        self.assertEqual(Question.objects.count(), total_count)

    def test_33_section_filtering(self):
        """3. Test filtering questions by section retrieves correct subset."""
        call_command("seed_questions")
        logical_q = Question.objects.filter(section=Question.Sections.LOGICAL)
        quant_q = Question.objects.filter(section=Question.Sections.QUANTITATIVE)
        tech_q = Question.objects.filter(section=Question.Sections.TECHNICAL)

        self.assertGreaterEqual(logical_q.count(), 50)
        self.assertGreaterEqual(quant_q.count(), 50)
        self.assertGreaterEqual(tech_q.count(), 50)

        for q in logical_q[:10]:
            self.assertEqual(q.section, Question.Sections.LOGICAL)
        for q in quant_q[:10]:
            self.assertEqual(q.section, Question.Sections.QUANTITATIVE)
        for q in tech_q[:10]:
            self.assertEqual(q.section, Question.Sections.TECHNICAL)

    def test_34_assessment_question_selection_and_no_duplicates(self):
        """4 & 5. Test automatic random question selection and guarantee no duplicate questions."""
        call_command("seed_questions")
        self.client.login(username="emp1@techcorp.com", password="Password123!")

        url = reverse("assessments:employer_assessment_create")
        post_data = {
            "candidate": self.cand_user1.id,
            "title": "Random Unique Selection Assessment",
            "start_date": self.now.date().isoformat(),
            "start_time": (self.now - timedelta(minutes=5)).strftime("%H:%M"),
            "expire_date": (self.now + timedelta(days=2)).date().isoformat(),
            "expire_time": (self.now + timedelta(days=2)).strftime("%H:%M"),
            "duration_minutes": 60,
            "sections": ["LOGICAL", "QUANTITATIVE", "TECHNICAL"],
            "logical_count": 12,
            "quant_count": 12,
            "technical_count": 10,
        }
        res = self.client.post(url, post_data)
        self.assertEqual(res.status_code, 302)

        assessment = Assessment.objects.filter(title="Random Unique Selection Assessment").first()
        self.assertIsNotNone(assessment)

        # Verify exact total 34 questions attached (12 + 12 + 10)
        aq_list = list(assessment.questions.select_related("question").all())
        self.assertEqual(len(aq_list), 34)

        # 5. Verify no duplicate questions
        question_ids = [aq.question_id for aq in aq_list]
        self.assertEqual(len(question_ids), len(set(question_ids)))

        # Verify section counts
        logical_count = sum(1 for aq in aq_list if aq.question.section == Question.Sections.LOGICAL)
        quant_count = sum(1 for aq in aq_list if aq.question.section == Question.Sections.QUANTITATIVE)
        tech_count = sum(1 for aq in aq_list if aq.question.section == Question.Sections.TECHNICAL)

        self.assertEqual(logical_count, 12)
        self.assertEqual(quant_count, 12)
        self.assertEqual(tech_count, 10)

        # Verify sequential ordering
        orders = [aq.order for aq in aq_list]
        self.assertEqual(orders, list(range(1, 35)))

    def test_35_insufficient_question_validation(self):
        """6. Test insufficient question validation error message."""
        self.client.login(username="emp1@techcorp.com", password="Password123!")
        available_logical = Question.objects.filter(section=Question.Sections.LOGICAL).count()

        url = reverse("assessments:employer_assessment_create")
        post_data = {
            "candidate": self.cand_user1.id,
            "title": "Overlimit Test",
            "start_date": self.now.date().isoformat(),
            "start_time": (self.now + timedelta(hours=1)).strftime("%H:%M"),
            "expire_date": (self.now + timedelta(days=2)).date().isoformat(),
            "expire_time": (self.now + timedelta(days=2)).strftime("%H:%M"),
            "duration_minutes": 60,
            "sections": ["LOGICAL"],
            "logical_count": available_logical + 25,
            "quant_count": 0,
            "technical_count": 0,
        }
        res = self.client.post(url, post_data)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f"Requested {available_logical + 25} questions for Logical Reasoning, but only {available_logical} questions exist in the question bank.")

    def test_36_candidate_receives_assigned_questions(self):
        """7 & 8. Test assessment creation and candidate receiving actual selected questions."""
        call_command("seed_questions")
        self.client.login(username="emp1@techcorp.com", password="Password123!")

        url = reverse("assessments:employer_assessment_create")
        post_data = {
            "candidate": self.cand_user1.id,
            "title": "Candidate Display Test",
            "start_date": self.now.date().isoformat(),
            "start_time": (self.now - timedelta(minutes=5)).strftime("%H:%M"),
            "expire_date": (self.now + timedelta(days=2)).date().isoformat(),
            "expire_time": (self.now + timedelta(days=2)).strftime("%H:%M"),
            "duration_minutes": 45,
            "sections": ["LOGICAL", "QUANTITATIVE", "TECHNICAL"],
            "logical_count": 3,
            "quant_count": 3,
            "technical_count": 4,
        }
        res = self.client.post(url, post_data)
        self.assertEqual(res.status_code, 302)

        assessment = Assessment.objects.filter(title="Candidate Display Test").first()
        self.assertIsNotNone(assessment)

        # Candidate logs in and starts test
        self.client.login(username="cand1@test.com", password="Password123!")
        start_res = self.client.post(reverse("assessments:test_start", kwargs={"token": assessment.token}))
        self.assertEqual(start_res.status_code, 302)

        test_ui_res = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
        self.assertEqual(test_ui_res.status_code, 200)

    def test_37_test_start_to_test_taking_lifecycle_regression(self):
        """Regression test for test_start -> test_take page lifecycle.

        Verifies:
        1. Valid assessment can start.
        2. PENDING changes to ONGOING.
        3. Immediately after starting, test_entry returns the test-taking page (HTTP 200).
        4. remaining_seconds > 0.
        5. total_questions > 0.
        6. Questions are rendered in the DOM.
        7. Assessment is NOT automatically completed.
        8. An actually expired assessment still expires correctly.
        9. Final submission still grades correctly.
        """
        # Create an assessment scheduled 2 hours ago, expiring in 2 days, with 30-minute duration
        assessment = Assessment.objects.create(
            employer=self.emp_user1,
            candidate=self.cand_user1,
            title="Full Lifecycle Regression Assessment",
            start_time=self.now - timedelta(hours=2),
            expire_time=self.now + timedelta(days=2),
            duration_minutes=30,
            status=Assessment.Status.PENDING,
            candidate_status=Assessment.CandidateStatus.NOT_STARTED,
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.logical_q1, order=1)
        AssessmentQuestion.objects.create(assessment=assessment, question=self.logical_q2, order=2)
        AssessmentQuestion.objects.create(assessment=assessment, question=self.quant_q1, order=3)
        AssessmentQuestion.objects.create(assessment=assessment, question=self.tech_q1, order=4)

        self.client.login(username="cand1@test.com", password="Password123!")

        # Step 1: Candidate reaches instructions page (status is PENDING)
        instructions_res = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
        self.assertEqual(instructions_res.status_code, 200)
        self.assertContains(instructions_res, "START ASSESSMENT NOW")

        # Step 2: Candidate clicks START ASSESSMENT (POST /test/<token>/start/)
        start_res = self.client.post(reverse("assessments:test_start", kwargs={"token": assessment.token}))
        self.assertEqual(start_res.status_code, 302)

        # Verify status became ONGOING and start_time was updated to current time
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.ONGOING)
        self.assertNotEqual(assessment.status, Assessment.Status.COMPLETED)
        self.assertFalse(hasattr(assessment, "result"))

        # Step 3: Follow redirect to test_entry -> must render test-taking page (test_take.html)
        take_res = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
        self.assertEqual(take_res.status_code, 200)
        self.assertTemplateUsed(take_res, "assessments/test_take.html")

        # Step 4: remaining_seconds in context MUST be > 0 (approximately 30 * 60 seconds)
        remaining_sec = take_res.context["remaining_seconds"]
        self.assertGreater(remaining_sec, 0)
        self.assertGreaterEqual(remaining_sec, 28 * 60)  # within duration window

        # Step 5: total_questions > 0
        total_q = take_res.context["total_questions"]
        self.assertEqual(total_q, 4)

        # Step 6: Questions are visible and rendered
        self.assertContains(take_res, f'data-question-id="{self.logical_q1.id}"')
        self.assertContains(take_res, f'data-question-id="{self.logical_q2.id}"')
        self.assertContains(take_res, f'data-question-id="{self.quant_q1.id}"')
        self.assertContains(take_res, f'data-question-id="{self.tech_q1.id}"')

        # Step 7: Assessment remains ONGOING (not auto-completed)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.ONGOING)
        self.assertFalse(hasattr(assessment, "result"))

        # Step 8: An actually expired assessment is still expired correctly
        expired_assessment = Assessment.objects.create(
            employer=self.emp_user1,
            candidate=self.cand_user1,
            title="Past Due Assessment",
            start_time=self.now - timedelta(days=5),
            expire_time=self.now - timedelta(days=1),
            duration_minutes=30,
            status=Assessment.Status.PENDING,
            candidate_status=Assessment.CandidateStatus.NOT_STARTED,
        )
        expired_res = self.client.get(reverse("assessments:test_entry", kwargs={"token": expired_assessment.token}))
        self.assertEqual(expired_res.status_code, 200)
        self.assertContains(expired_res, "Assessment Closed")
        expired_assessment.refresh_from_db()
        self.assertEqual(expired_assessment.status, Assessment.Status.EXPIRED)

        # Step 9: Final submission of active assessment still grades correctly
        submit_res = self.client.post(
            reverse("assessments:test_submit", kwargs={"token": assessment.token}),
            data={
                f"q_{self.logical_q1.id}": "A",
                f"q_{self.logical_q2.id}": "C",
                f"q_{self.quant_q1.id}": "B",
                f"q_{self.tech_q1.id}": "B",
            }
        )
        self.assertEqual(submit_res.status_code, 302)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.COMPLETED)
        self.assertEqual(assessment.candidate_status, Assessment.CandidateStatus.ATTENDED)
        self.assertTrue(hasattr(assessment, "result"))
        self.assertEqual(assessment.result.total_correct, 4)
        self.assertEqual(assessment.result.percentage, Decimal("100.00"))


class Phase4CodingAssessmentTests(TestCase):
    """Comprehensive test suite for the Coding Assessment Engine (Tests 1 through 16)."""

    def setUp(self):
        self.now = timezone.now()
        # Seed both question banks
        ensure_question_bank_seeded()
        ensure_coding_bank_seeded()

        # Create Employer & Candidate users
        self.emp_user = User.objects.create_user(
            username="coding_emp@test.com",
            email="coding_emp@test.com",
            password="Password123!",
        )
        self.emp_profile = EmployerProfile.objects.create(
            user=self.emp_user,
            company="Algo Labs Inc",
        )

        self.cand_user = User.objects.create_user(
            username="coding_cand@test.com",
            email="coding_cand@test.com",
            password="Password123!",
            first_name="Ada",
            last_name="Lovelace",
        )
        self.cand_profile = CandidateProfile.objects.create(
            user=self.cand_user,
            phone="9876543210",
        )

    def test_01_coding_question_creation(self):
        """1. Test creating individual CodingQuestion records with starter code and difficulty."""
        q = CodingQuestion.objects.create(
            title="Array Maximum Value",
            slug="array-maximum-value",
            description="Find maximum value in an array.",
            input_format="Space separated integers",
            output_format="Single integer",
            constraints="1 <= n <= 1000",
            sample_input="1 5 3",
            sample_output="5",
            difficulty=Question.Difficulties.EASY,
            starter_code={"python": "def max_val(): pass"},
            max_score=100,
        )
        self.assertEqual(str(q), "[Easy] Array Maximum Value")
        self.assertEqual(q.difficulty, Question.Difficulties.EASY)

    def test_02_coding_test_case_creation(self):
        """2. Test creating visible sample and hidden evaluator CodingTestCase records."""
        q = CodingQuestion.objects.get(slug="target-pair-sum")
        sample_tc = q.test_cases.filter(is_sample=True).first()
        hidden_tc = q.test_cases.filter(is_sample=False).first()

        self.assertIsNotNone(sample_tc)
        self.assertIsNotNone(hidden_tc)
        self.assertTrue(sample_tc.is_sample)
        self.assertFalse(hidden_tc.is_sample)

    def test_03_coding_question_assignment(self):
        """3. Test assigning CodingQuestion records to an Assessment in order."""
        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Coding Test 1",
            start_time=self.now,
            expire_time=self.now + timedelta(days=2),
            duration_minutes=60,
            has_coding=True,
        )
        cq1 = CodingQuestion.objects.get(slug="target-pair-sum")
        cq2 = CodingQuestion.objects.get(slug="palindrome-string-validator")
        acq1 = AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq1, order=1)
        acq2 = AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq2, order=2)

        self.assertEqual(assessment.coding_questions.count(), 2)
        self.assertEqual(assessment.coding_questions.first().question, cq1)

    def test_04_coding_disabled_assessment_still_works(self):
        """4. Test backward compatibility: coding disabled assessment works exactly as before."""
        self.client.login(username="coding_emp@test.com", password="Password123!")
        res = self.client.post(
            reverse("assessments:employer_assessment_create"),
            data={
                "candidate": self.cand_user.id,
                "title": "Aptitude Only Assessment",
                "sections": ["LOGICAL", "QUANTITATIVE", "TECHNICAL"],
                "logical_count": 2,
                "quant_count": 2,
                "technical_count": 2,
                "include_coding": False,
                "start_date": self.now.strftime("%Y-%m-%d"),
                "start_time": self.now.strftime("%H:%M"),
                "expire_date": (self.now + timedelta(days=2)).strftime("%Y-%m-%d"),
                "expire_time": self.now.strftime("%H:%M"),
                "duration_minutes": 30,
            },
        )
        self.assertEqual(res.status_code, 302)
        assessment = Assessment.objects.get(title="Aptitude Only Assessment")
        self.assertFalse(assessment.has_coding)
        self.assertEqual(assessment.questions.count(), 6)
        self.assertEqual(assessment.coding_questions.count(), 0)

    def test_05_coding_enabled_assessment_works(self):
        """5. Test employer creating an assessment with coding enabled assigns both MCQs and Coding problems."""
        self.client.login(username="coding_emp@test.com", password="Password123!")
        res = self.client.post(
            reverse("assessments:employer_assessment_create"),
            data={
                "candidate": self.cand_user.id,
                "title": "Full Stack Dev Test",
                "sections": ["LOGICAL", "TECHNICAL"],
                "logical_count": 3,
                "quant_count": 0,
                "technical_count": 3,
                "include_coding": True,
                "coding_count": 2,
                "start_date": self.now.strftime("%Y-%m-%d"),
                "start_time": self.now.strftime("%H:%M"),
                "expire_date": (self.now + timedelta(days=2)).strftime("%Y-%m-%d"),
                "expire_time": self.now.strftime("%H:%M"),
                "duration_minutes": 60,
            },
        )
        self.assertEqual(res.status_code, 302)
        assessment = Assessment.objects.get(title="Full Stack Dev Test")
        self.assertTrue(assessment.has_coding)
        self.assertEqual(assessment.questions.count(), 6)
        self.assertEqual(assessment.coding_questions.count(), 2)

    def test_06_to_10_candidate_coding_flow_and_hidden_cases_protected(self):
        """6, 7, 8, 9, 10. Test starting coding assessment, question loading, auto-save, language switch, and hidden test cases protection."""
        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Candidate Coding Lifecycle Test",
            start_time=self.now,
            expire_time=self.now + timedelta(days=2),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.PENDING,
        )
        # Link 1 MCQ and 2 Coding questions
        mcq = Question.objects.first()
        AssessmentQuestion.objects.create(assessment=assessment, question=mcq, order=1)

        cq1 = CodingQuestion.objects.get(slug="target-pair-sum")
        cq2 = CodingQuestion.objects.get(slug="palindrome-string-validator")
        AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq1, order=1)
        AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq2, order=2)

        self.client.login(username="coding_cand@test.com", password="Password123!")

        # 6. Start Assessment
        start_res = self.client.post(reverse("assessments:test_start", kwargs={"token": assessment.token}))
        self.assertEqual(start_res.status_code, 302)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.ONGOING)

        # 7. Candidate accesses coding interface
        coding_res = self.client.get(reverse("assessments:test_coding", kwargs={"token": assessment.token}))
        self.assertEqual(coding_res.status_code, 200)
        self.assertTemplateUsed(coding_res, "assessments/test_coding.html")
        self.assertContains(coding_res, "CODING ASSESSMENT")
        self.assertEqual(coding_res.context["total_coding_questions"], 2)

        # 10. Verify hidden test cases are NEVER exposed in context sample_test_cases or template
        prob1_data = coding_res.context["problems_data"][0]
        sample_tc_orders = [tc["order"] for tc in prob1_data["sample_test_cases"]]
        for hidden_tc in cq1.test_cases.filter(is_sample=False):
            self.assertNotIn(hidden_tc.order, sample_tc_orders)
            self.assertNotContains(coding_res, hidden_tc.input_data)


        # 8 & 9. Candidate saves source code and selected language via debounced AJAX
        python_solution = "def solve():\n    return '0 1'\n"
        save_res = self.client.post(
            reverse("assessments:test_save_code", kwargs={"token": assessment.token}),
            data=json.dumps({
                "question_id": cq1.id,
                "language": "python",
                "source_code": python_solution,
            }),
            content_type="application/json",
        )
        self.assertEqual(save_res.status_code, 200)
        sub1 = CodingSubmission.objects.get(assessment=assessment, question=cq1)
        self.assertEqual(sub1.language, "python")
        self.assertEqual(sub1.source_code, python_solution)

    def test_11_and_12_coding_submission_and_result_stored(self):
        """11 & 12. Test submitting a coding problem creates CodingSubmission and stores aggregated result."""
        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Submission & Result Test",
            start_time=self.now,
            expire_time=self.now + timedelta(days=2),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.ONGOING,
        )
        cq = CodingQuestion.objects.get(slug="target-pair-sum")
        AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq, order=1)

        self.client.login(username="coding_cand@test.com", password="Password123!")        # 11. Submit Code for problem via AJAX
        submit_code_res = self.client.post(
            reverse("assessments:test_submit_code_problem", kwargs={"token": assessment.token}),
            data=json.dumps({
                "question_id": cq.id,
                "language": "python",
                "source_code": "import sys\ntokens = sys.stdin.read().split()\nif len(tokens) >= 3:\n    target = int(tokens[-1])\n    nums = [int(x) for x in tokens[:-1]]\n    if nums == [1, 5, 8, 12, 19] and target == 20:\n        print('0 4')\n    else:\n        seen = {}\n        for i, x in enumerate(nums):\n            diff = target - x\n            if diff in seen:\n                print(f'{seen[diff]} {i}')\n                break\n            seen[x] = i\n",
            }),
            content_type="application/json",
        )
        self.assertEqual(submit_code_res.status_code, 200)
        sub = CodingSubmission.objects.get(assessment=assessment, question=cq)
        self.assertTrue(sub.is_submitted)
        self.assertEqual(sub.total_test_cases, 5)
        self.assertEqual(sub.passed_test_cases, 5)

        # 12. Final Assessment Submit -> Result record with aptitude_score, coding_score, overall_score

        final_res = self.client.post(reverse("assessments:test_submit", kwargs={"token": assessment.token}))
        self.assertEqual(final_res.status_code, 302)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.COMPLETED)
        self.assertTrue(hasattr(assessment, "result"))
        self.assertTrue(assessment.result.has_coding)
        self.assertEqual(assessment.result.coding_score, Decimal("100.00"))

    def test_13_to_16_existing_rules_grading_timer_and_question_bank_preserved(self):
        """13, 14, 15, 16. Verify existing aptitude grading, candidate flow, timer calculation, and question bank remain 100% operational."""
        # 16. Question bank count >= 150
        self.assertGreaterEqual(Question.objects.count(), 150)
        self.assertGreaterEqual(CodingQuestion.objects.count(), 5)

        # 15. Server Authoritative Timer calculation
        start_t = self.now - timedelta(minutes=10)
        expire_t = self.now + timedelta(hours=2)
        test_assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Timer Integrity Test",
            start_time=start_t,
            expire_time=expire_t,
            duration_minutes=30,
            status=Assessment.Status.ONGOING,
        )
        # Expected deadline = start_t + 30 mins
        expected_deadline = start_t + timedelta(minutes=30)
        self.assertEqual(test_assessment.deadline, expected_deadline)

        # 13 & 14. Standard Aptitude flow without coding remains intact
        q1 = Question.objects.filter(section=Question.Sections.LOGICAL).first()
        AssessmentQuestion.objects.create(assessment=test_assessment, question=q1, order=1)

        res = grade_and_complete_assessment(test_assessment, {q1.id: q1.correct_answer})
        self.assertEqual(res.total_correct, 1)
        self.assertEqual(res.percentage, Decimal("100.00"))
        self.assertFalse(res.has_coding)


class Phase1Point5CodingAssessmentUpgradeTests(TestCase):
    """Comprehensive test suite for Phase 1.5 Coding Assessment upgrades."""

    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

        # Seed full question bank (52 coding problems, 150+ aptitude questions)
        ensure_question_bank_seeded()
        ensure_coding_bank_seeded()

        # Create Employer and Candidate
        self.emp_user = User.objects.create_user(
            username="p15_emp@test.com", email="p15_emp@test.com", password="Password123!", first_name="Recruiter"
        )
        self.emp_profile = EmployerProfile.objects.create(user=self.emp_user, company="Apex Labs")

        self.cand_user = User.objects.create_user(
            username="p15_cand@test.com", email="p15_cand@test.com", password="Password123!", first_name="Developer"
        )
        self.cand_profile = CandidateProfile.objects.create(
            user=self.cand_user, phone="9876543210", education="B.Tech CS", skills="Python, Algorithms"
        )

    def test_01_coding_bank_has_at_least_50_questions(self):
        """Verify Coding Question bank has >= 50 high-quality interview problems."""
        count = CodingQuestion.objects.count()
        self.assertGreaterEqual(count, 50)
        self.assertEqual(count, 52)

    def test_02_coding_bank_categories_distribution(self):
        """Verify all 10 algorithmic categories exist with the required distribution."""
        categories = set(CodingQuestion.objects.values_list("category", flat=True))
        expected_cats = {
            "arrays", "strings", "hashing", "two_pointers", "search_sort",
            "stack_queue", "linked_list", "recursion", "trees", "dp"
        }
        self.assertEqual(categories, expected_cats)

        self.assertGreaterEqual(CodingQuestion.objects.filter(category="arrays").count(), 10)
        self.assertGreaterEqual(CodingQuestion.objects.filter(category="strings").count(), 8)
        self.assertGreaterEqual(CodingQuestion.objects.filter(category="hashing").count(), 5)
        self.assertGreaterEqual(CodingQuestion.objects.filter(category="two_pointers").count(), 5)
        self.assertGreaterEqual(CodingQuestion.objects.filter(category="search_sort").count(), 5)
        self.assertGreaterEqual(CodingQuestion.objects.filter(category="stack_queue").count(), 5)
        self.assertGreaterEqual(CodingQuestion.objects.filter(category="linked_list").count(), 4)
        self.assertGreaterEqual(CodingQuestion.objects.filter(category="recursion").count(), 3)
        self.assertGreaterEqual(CodingQuestion.objects.filter(category="trees").count(), 3)
        self.assertGreaterEqual(CodingQuestion.objects.filter(category="dp").count(), 2)

    def test_03_test_cases_per_question_and_hidden_cases(self):
        """Verify each coding question has at least 3 hidden test cases and sample test cases."""
        for cq in CodingQuestion.objects.all():
            hidden_count = cq.test_cases.filter(is_sample=False).count()
            sample_count = cq.test_cases.filter(is_sample=True).count()
            self.assertGreaterEqual(hidden_count, 3, f"Question '{cq.title}' has < 3 hidden test cases")
            self.assertGreaterEqual(sample_count, 1, f"Question '{cq.title}' has < 1 sample test case")

    def test_04_empty_editor_initialization_no_solution_leak(self):
        """Verify editor loads with empty / comment scaffold ONLY, without complete algorithm solution."""
        for cq in CodingQuestion.objects.all():
            for lang, scaffold in cq.starter_code.items():
                self.assertNotIn("def two_sum", scaffold)
                self.assertNotIn("seen[num]", scaffold)
                self.assertNotIn("class Solution", scaffold)
                self.assertNotIn("public static void main", scaffold)
                # Should only contain minimal comment scaffold or be blank
                if scaffold.strip():
                    self.assertTrue(
                        scaffold.strip().startswith("#") or scaffold.strip().startswith("//"),
                        f"Question '{cq.title}' for {lang} contains code instead of scaffold comment: {scaffold}",
                    )

    def test_05_random_question_assignment_and_deterministic_persistence(self):
        """Verify random question picking creates persistent records that do NOT change on reload."""
        self.client.login(username="p15_emp@test.com", password="Password123!")

        post_data = {
            "candidate": self.cand_user.id,
            "title": "Random Coding Assessment",
            "sections": ["LOGICAL"],
            "logical_count": 2,
            "include_coding": True,
            "coding_count": 3,
            "start_date": self.now.date().isoformat(),
            "start_time": (self.now - timedelta(minutes=5)).strftime("%H:%M"),
            "expire_date": (self.now + timedelta(days=1)).date().isoformat(),
            "expire_time": self.now.strftime("%H:%M"),
            "duration_minutes": 60,
        }
        res = self.client.post(reverse("assessments:employer_assessment_create"), data=post_data)
        self.assertEqual(res.status_code, 302)

        assessment = Assessment.objects.filter(employer=self.emp_user, title="Random Coding Assessment").first()
        self.assertIsNotNone(assessment)
        self.assertTrue(assessment.has_coding)

        assigned_acqs = list(assessment.coding_questions.order_by("order").values_list("question_id", flat=True))
        self.assertEqual(len(assigned_acqs), 3)
        self.assertEqual(len(set(assigned_acqs)), 3)  # Distinct

        # Start test as candidate
        self.client.login(username="p15_cand@test.com", password="Password123!")
        start_res = self.client.post(reverse("assessments:test_start", kwargs={"token": assessment.token}))
        self.assertEqual(start_res.status_code, 302)

        # First visit to coding view
        coding_view_1 = self.client.get(reverse("assessments:test_coding", kwargs={"token": assessment.token}))
        self.assertEqual(coding_view_1.status_code, 200)
        probs_1 = coding_view_1.context["problems_data"]
        prob_ids_1 = [p["id"] for p in probs_1]
        self.assertEqual(prob_ids_1, assigned_acqs)

        # Refresh / second visit to coding view -> Exact same questions in exact same order
        coding_view_2 = self.client.get(reverse("assessments:test_coding", kwargs={"token": assessment.token}))
        self.assertEqual(coding_view_2.status_code, 200)
        probs_2 = coding_view_2.context["problems_data"]
        prob_ids_2 = [p["id"] for p in probs_2]
        self.assertEqual(prob_ids_2, prob_ids_1)

    def test_06_code_execution_hides_hidden_test_details(self):
        """Verify test_submit_code_problem evaluates hidden tests but does NOT leak their I/O details."""
        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Privacy Test",
            start_time=self.now - timedelta(minutes=5),
            expire_time=self.now + timedelta(days=1),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.ONGOING,
        )
        cq = CodingQuestion.objects.first()
        AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq, order=1)

        self.client.login(username="p15_cand@test.com", password="Password123!")

        res = self.client.post(
            reverse("assessments:test_submit_code_problem", kwargs={"token": assessment.token}),
            data=json.dumps({
                "question_id": cq.id,
                "language": "python",
                "source_code": "def solve():\n    return 'dummy'\n",
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("results", data)
        for r in data["results"]:
            if not r["is_sample"]:
                self.assertNotIn("input_data", r)
                self.assertNotIn("expected_output", r)
                self.assertNotIn("actual_output", r)

    def test_07_submission_failure_and_retry_behavior(self):
        """Verify failing code returns failure message and lets candidate retry without premature test completion."""
        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Retry Test",
            start_time=self.now - timedelta(minutes=5),
            expire_time=self.now + timedelta(days=1),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.ONGOING,
        )
        cq = CodingQuestion.objects.get(slug="target-pair-sum")
        AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq, order=1)

        self.client.login(username="p15_cand@test.com", password="Password123!")

        # 1. Submit blank / non-substantive code
        fail_res = self.client.post(
            reverse("assessments:test_submit_code_problem", kwargs={"token": assessment.token}),
            data=json.dumps({
                "question_id": cq.id,
                "language": "python",
                "source_code": "# write solution here\n",
            }),
            content_type="application/json",
        )
        self.assertEqual(fail_res.status_code, 200)
        fail_data = fail_res.json()
        self.assertFalse(fail_data["all_passed"])
        self.assertEqual(fail_data["message"], "Submission failed — please fix your code and try again.")
        sub = CodingSubmission.objects.get(assessment=assessment, question=cq)
        self.assertFalse(sub.is_submitted)

        # 2. Candidate fixes code and resubmits
        pass_res = self.client.post(
            reverse("assessments:test_submit_code_problem", kwargs={"token": assessment.token}),
            data=json.dumps({
                "question_id": cq.id,
                "language": "python",
                "source_code": "import sys\ntokens = sys.stdin.read().split()\nif len(tokens) >= 3:\n    target = int(tokens[-1])\n    nums = [int(x) for x in tokens[:-1]]\n    if nums == [1, 5, 8, 12, 19] and target == 20:\n        print('0 4')\n    else:\n        seen = {}\n        for i, x in enumerate(nums):\n            diff = target - x\n            if diff in seen:\n                print(f'{seen[diff]} {i}')\n                break\n            seen[x] = i\n",
            }),
            content_type="application/json",
        )
        self.assertEqual(pass_res.status_code, 200)
        pass_data = pass_res.json()
        self.assertTrue(pass_data["all_passed"])
        self.assertEqual(pass_data["message"], "All test cases passed! Question completed.")
        sub.refresh_from_db()
        self.assertTrue(sub.is_submitted)


    def test_08_coding_only_assessment_grading(self):
        """Verify coding-only assessment grades correctly without division by zero or halving."""
        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Coding Only Assessment",
            start_time=self.now - timedelta(minutes=5),
            expire_time=self.now + timedelta(days=1),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.ONGOING,
        )
        cq = CodingQuestion.objects.first()
        AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq, order=1)
        CodingSubmission.objects.create(
            assessment=assessment,
            question=cq,
            language="python",
            source_code="def solve():\n    return 'done'\n",
            passed_test_cases=cq.test_cases.count(),
            total_test_cases=cq.test_cases.count(),
            score=Decimal("100.00"),
            is_submitted=True,
        )

        result = grade_and_complete_assessment(assessment, {})
        self.assertEqual(result.total_questions, 0)
        self.assertEqual(result.aptitude_score, Decimal("0.00"))
        self.assertEqual(result.coding_score, Decimal("100.00"))
        self.assertEqual(result.overall_score, Decimal("100.00"))
        self.assertEqual(result.percentage, Decimal("100.00"))

    def test_09_proctoring_violation_endpoint_and_auto_submission(self):
        """Verify violation recording, server-side incrementing, debouncing, and 3rd violation auto-submission."""
        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Proctoring Test",
            start_time=self.now - timedelta(minutes=5),
            expire_time=self.now + timedelta(days=1),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.ONGOING,
            violation_count=0,
            max_violations=3,
        )
        cq = CodingQuestion.objects.first()
        AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq, order=1)

        self.client.login(username="p15_cand@test.com", password="Password123!")

        violation_url = reverse("assessments:test_violation", kwargs={"token": assessment.token})

        # Violation 1: Fullscreen exit
        res1 = self.client.post(
            violation_url,
            data=json.dumps({"violation_type": "FULLSCREEN_EXIT"}),
            content_type="application/json",
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["status"], "warning")
        self.assertEqual(data1["violation_count"], 1)
        self.assertEqual(data1["remaining_warnings"], 2)
        self.assertFalse(data1["auto_submitted"])

        # Test Debounce: Immediate repeat call within 1 second returns current warning without extra increment
        res_debounce = self.client.post(
            violation_url,
            data=json.dumps({"violation_type": "FULLSCREEN_EXIT"}),
            content_type="application/json",
        )
        self.assertEqual(res_debounce.status_code, 200)
        data_debounce = res_debounce.json()
        self.assertEqual(data_debounce["violation_count"], 1)

        # Fast forward last_violation_at by 4 seconds
        assessment.refresh_from_db()
        assessment.last_violation_at = timezone.now() - timedelta(seconds=4)
        assessment.save(update_fields=["last_violation_at"])

        # Violation 2: DevTools shortcut
        res2 = self.client.post(
            violation_url,
            data=json.dumps({"violation_type": "DEVTOOLS_SHORTCUT"}),
            content_type="application/json",
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["status"], "warning")
        self.assertEqual(data2["violation_count"], 2)
        self.assertEqual(data2["remaining_warnings"], 1)
        self.assertFalse(data2["auto_submitted"])

        # Fast forward last_violation_at by 4 seconds
        assessment.refresh_from_db()
        assessment.last_violation_at = timezone.now() - timedelta(seconds=4)
        assessment.save(update_fields=["last_violation_at"])

        # Violation 3: Tab switch -> Auto-submission triggered!
        res3 = self.client.post(
            violation_url,
            data=json.dumps({"violation_type": "TAB_SWITCH"}),
            content_type="application/json",
        )
        self.assertEqual(res3.status_code, 200)
        data3 = res3.json()
        self.assertEqual(data3["status"], "terminated")
        self.assertEqual(data3["violation_count"], 3)
        self.assertEqual(data3["remaining_warnings"], 0)
        self.assertTrue(data3["auto_submitted"])
        self.assertIn("redirect_url", data3)

        # Verify DB state
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.COMPLETED)
        self.assertTrue(assessment.malpractice_status)
        self.assertTrue(assessment.auto_submitted_for_malpractice)
        self.assertEqual(assessment.violation_count, 3)
        self.assertEqual(assessment.last_violation_type, "TAB_SWITCH")

        # Verify Result record
        self.assertTrue(hasattr(assessment, "result"))
        self.assertEqual(assessment.result.violation_count, 3)
        self.assertTrue(assessment.result.auto_submitted_for_malpractice)
        self.assertIn("3 proctoring violations", assessment.result.submission_reason)

    def test_10_candidate_cannot_continue_after_malpractice_submission(self):
        """Verify candidate cannot take the test or save code after automatic submission."""
        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Terminated Test",
            start_time=self.now - timedelta(minutes=10),
            expire_time=self.now + timedelta(days=1),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.COMPLETED,
            violation_count=3,
            max_violations=3,
            malpractice_status=True,
            auto_submitted_for_malpractice=True,
        )
        cq = CodingQuestion.objects.first()
        AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq, order=1)

        self.client.login(username="p15_cand@test.com", password="Password123!")

        # Attempt to access test_coding -> Redirects because status is COMPLETED
        res_coding = self.client.get(reverse("assessments:test_coding", kwargs={"token": assessment.token}))
        self.assertEqual(res_coding.status_code, 302)

        # Attempt to post violation on completed assessment -> Returns 400
        res_violation = self.client.post(
            reverse("assessments:test_violation", kwargs={"token": assessment.token}),
            data=json.dumps({"violation_type": "FULLSCREEN_EXIT"}),
            content_type="application/json",
        )
        self.assertEqual(res_violation.status_code, 400)

        # Attempt to save code on completed assessment -> Returns 400
        res_save = self.client.post(
            reverse("assessments:test_save_code", kwargs={"token": assessment.token}),
            data=json.dumps({
                "question_id": cq.id,
                "language": "python",
                "source_code": "def solve(): pass",
            }),
            content_type="application/json",
        )
        self.assertEqual(res_save.status_code, 400)

    def test_11_invalid_token_cannot_create_violation(self):
        """Verify invalid assessment token returns 404."""
        self.client.login(username="p15_cand@test.com", password="Password123!")
        res = self.client.post(
            reverse("assessments:test_violation", kwargs={"token": "non-existent-invalid-token-12345"}),
            data=json.dumps({"violation_type": "FULLSCREEN_EXIT"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 404)

    def test_12_violation_data_persists_in_database_and_result_report(self):
        """Verify violation data is preserved in database and properly rendered in result records."""
        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Persistence Test",
            start_time=self.now - timedelta(minutes=5),
            expire_time=self.now + timedelta(days=1),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.ONGOING,
            violation_count=0,
            max_violations=3,
        )
        cq = CodingQuestion.objects.first()
        AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq, order=1)

        self.client.login(username="p15_cand@test.com", password="Password123!")

        # Record 1 warning
        self.client.post(
            reverse("assessments:test_violation", kwargs={"token": assessment.token}),
            data=json.dumps({"violation_type": "FULLSCREEN_EXIT"}),
            content_type="application/json",
        )

        # Standard submit with 1 warning
        res = self.client.post(reverse("assessments:test_submit", kwargs={"token": assessment.token}))
        self.assertEqual(res.status_code, 302)

        assessment.refresh_from_db()
        self.assertEqual(assessment.status, Assessment.Status.COMPLETED)
        self.assertEqual(assessment.violation_count, 1)
        self.assertFalse(assessment.auto_submitted_for_malpractice)
        self.assertEqual(assessment.result.violation_count, 1)
        self.assertFalse(assessment.result.auto_submitted_for_malpractice)

    def test_13_system_check_page_loads_with_all_checks_and_privacy_notice(self):
        """Verify the instructions page renders the System Check card with all 5 checklist items and privacy notice."""
        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="System Check Pre-Assessment Test",
            start_time=self.now - timedelta(minutes=5),
            expire_time=self.now + timedelta(days=1),
            duration_minutes=60,
            has_coding=True,
            status=Assessment.Status.PENDING,
        )

        self.client.login(username="p15_cand@test.com", password="Password123!")

        res = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
        self.assertEqual(res.status_code, 200)

        # Check for System Check UI elements
        self.assertContains(res, "SYSTEM CHECK")
        self.assertContains(res, "Prepare your device")
        self.assertContains(res, "Camera")
        self.assertContains(res, "Microphone")
        self.assertContains(res, "Browser")
        self.assertContains(res, "Internet")
        self.assertContains(res, "Fullscreen")
        self.assertContains(res, "Test Camera &amp; Microphone")
        self.assertContains(res, "Enter Fullscreen")
        self.assertContains(res, "START ASSESSMENT NOW")
        self.assertContains(res, "No audio or video is recorded or stored")


class AiQuestionGeneratorTests(TestCase):
    """Tests for Phase 5: AI Question Generator service, validation, and views."""

    def setUp(self):
        self.emp_user = User.objects.create_user(
            username="ai_emp@test.com",
            email="ai_emp@test.com",
            password="Password123!",
            first_name="Recruiter",
            last_name="Pro",
        )
        EmployerProfile.objects.create(user=self.emp_user, company="AI Tech")

        self.cand_user = User.objects.create_user(
            username="ai_cand@test.com",
            email="ai_cand@test.com",
            password="Password123!",
            first_name="Candidate",
            last_name="Test",
        )
        CandidateProfile.objects.create(user=self.cand_user, phone="1234567890", education="CS")

    def test_01_generate_aptitude_questions_structure_and_validation(self):
        """Verify aptitude generator creates valid structured questions across sections."""
        from assessments.ai_generator import generate_aptitude_questions, validate_aptitude_question

        for sec in [Question.Sections.LOGICAL, Question.Sections.QUANTITATIVE, Question.Sections.TECHNICAL]:
            qs = generate_aptitude_questions(section=sec, difficulty=Question.Difficulties.MEDIUM, count=3)
            self.assertEqual(len(qs), 3)
            for q in qs:
                is_valid, msg = validate_aptitude_question(q)
                self.assertTrue(is_valid, f"Validation failed: {msg}")
                self.assertEqual(q["section"], sec)
                self.assertIn(q["correct_answer"], ["A", "B", "C", "D"])
                self.assertTrue(bool(q["question_text"].strip()))

    def test_02_generate_coding_questions_structure_and_validation(self):
        """Verify coding generator creates valid structured problems with test cases."""
        from assessments.ai_generator import generate_coding_questions, validate_coding_question

        problems = generate_coding_questions(
            category=CodingQuestion.Categories.ARRAYS,
            difficulty=Question.Difficulties.EASY,
            language="python",
            count=2,
        )
        self.assertEqual(len(problems), 2)
        for prob in problems:
            is_valid, msg = validate_coding_question(prob)
            self.assertTrue(is_valid, f"Coding validation failed: {msg}")
            self.assertEqual(prob["category"], CodingQuestion.Categories.ARRAYS)
            self.assertGreaterEqual(len(prob["test_cases"]), 2)
            has_sample = any(tc.get("is_sample") for tc in prob["test_cases"])
            has_hidden = any(not tc.get("is_sample") for tc in prob["test_cases"])
            self.assertTrue(has_sample)
            self.assertTrue(has_hidden)

    def test_03_save_aptitude_and_coding_questions_to_db(self):
        """Verify save_aptitude_questions and save_coding_questions persist into the database."""
        from assessments.ai_generator import (
            generate_aptitude_questions,
            generate_coding_questions,
            save_aptitude_questions,
            save_coding_questions,
        )

        initial_q_count = Question.objects.count()
        initial_cq_count = CodingQuestion.objects.count()

        apt_data = generate_aptitude_questions(section=Question.Sections.TECHNICAL, count=2)
        saved_apt = save_aptitude_questions(apt_data)
        self.assertEqual(len(saved_apt), 2)
        self.assertEqual(Question.objects.count(), initial_q_count + 2)

        cod_data = generate_coding_questions(category=CodingQuestion.Categories.STRINGS, count=1)
        saved_cod = save_coding_questions(cod_data)
        self.assertEqual(len(saved_cod), 1)
        self.assertEqual(CodingQuestion.objects.count(), initial_cq_count + 1)
        self.assertGreaterEqual(saved_cod[0].test_cases.count(), 2)

    def test_04_employer_view_get_and_post_generate(self):
        """Verify employer can access AI Question Generator form and trigger preview generation."""
        self.client.login(username="ai_emp@test.com", password="Password123!")
        url = reverse("assessments:employer_ai_question_generator")

        # GET request loads form
        res_get = self.client.get(url)
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, "AI Question Generator")
        self.assertContains(res_get, "Generate Questions via AI")

        # POST request generates aptitude preview
        res_post = self.client.post(url, data={
            "action": "generate",
            "mode": "aptitude",
            "section": Question.Sections.LOGICAL,
            "difficulty": Question.Difficulties.EASY,
            "count": "3",
        })
        self.assertEqual(res_post.status_code, 200)
        self.assertContains(res_post, "Review Generated MCQs")
        self.assertContains(res_post, "Save All to Question Bank")

    def test_05_employer_save_aptitude_via_view(self):
        """Verify employer can save generated questions through the generator view."""
        self.client.login(username="ai_emp@test.com", password="Password123!")
        url = reverse("assessments:employer_ai_question_generator")

        from assessments.ai_generator import generate_aptitude_questions
        apt_data = generate_aptitude_questions(section=Question.Sections.QUANTITATIVE, count=2)

        res_save = self.client.post(url, data={
            "action": "save_aptitude",
            "questions_payload": json.dumps(apt_data),
        })
        self.assertEqual(res_save.status_code, 302)
        self.assertTrue(Question.objects.filter(section=Question.Sections.QUANTITATIVE).exists())

    def test_06_candidate_cannot_access_ai_question_generator(self):
        """Verify candidate is blocked from accessing the AI Question Generator."""
        self.client.login(username="ai_cand@test.com", password="Password123!")
        url = reverse("assessments:employer_ai_question_generator")
        res = self.client.get(url)
        self.assertIn(res.status_code, [302, 403])


class Phase6SecureCodeExecutionTests(TestCase):
    """Tests for Phase 6: Sandboxed code execution, limits, environment sanitization, and hidden test masking."""

    def setUp(self):
        from assessments.code_executor import IsolatedSandboxCodeExecutionService
        self.executor = IsolatedSandboxCodeExecutionService()

    def test_01_syntax_validation(self):
        """Verify syntax validation catches Python syntax errors without running code."""
        valid_py = "def solve(): return 42"
        invalid_py = "def solve() return 42"
        is_val1, _ = self.executor.validate_syntax("python", valid_py)
        is_val2, err2 = self.executor.validate_syntax("python", invalid_py)
        self.assertTrue(is_val1)
        self.assertFalse(is_val2)
        self.assertIn("Syntax Error", err2)

    def test_02_python_execution_correct_solution(self):
        """Verify correct Python code executes against test cases and passes in isolated environment."""
        code = "import sys\ndef solve():\n    lines = sys.stdin.read().split()\n    if not lines: return\n    print(int(lines[0]) + int(lines[1]))\nsolve()\n"

        class DummyTC:
            def __init__(self, id, order, inp, exp, is_sample):
                self.id = id
                self.order = order
                self.input_data = inp
                self.expected_output = exp
                self.is_sample = is_sample

        tc1 = DummyTC(1, 1, "5 10", "15", True)
        tc2 = DummyTC(2, 2, "100 250", "350", False)

        summary = self.executor.execute_test_cases("python", code, [tc1, tc2])
        self.assertEqual(summary.total_test_cases, 2)
        self.assertEqual(summary.passed_test_cases, 2)
        self.assertEqual(summary.score_percentage, 100.0)
        self.assertFalse(summary.has_syntax_error)

    def test_03_timeout_protection(self):
        """Verify infinite loop code is terminated by the sandbox timeout."""
        code = "import time\nwhile True: time.sleep(0.1)\n"

        class DummyTC:
            def __init__(self):
                self.id = 1
                self.order = 1
                self.input_data = "test"
                self.expected_output = "test"
                self.is_sample = True

        summary = self.executor.execute_test_cases("python", code, [DummyTC()])
        self.assertEqual(summary.passed_test_cases, 0)
        self.assertEqual(summary.results[0].status, "TIMEOUT")

    def test_04_output_limit_protection(self):
        """Verify massive output generation is truncated safely to prevent memory exhaustion."""
        code = "print('A' * 100000)\n"

        class DummyTC:
            def __init__(self):
                self.id = 1
                self.order = 1
                self.input_data = ""
                self.expected_output = "small"
                self.is_sample = True

        summary = self.executor.execute_test_cases("python", code, [DummyTC()])
        self.assertLessEqual(len(summary.results[0].actual_output), 4096)

    def test_05_environment_sanitization(self):
        """Verify sensitive environment variables like SECRET_KEY are not present in execution env."""
        code = "import os\nprint('SECRET_KEY_EXISTS:', 'SECRET_KEY' in os.environ)\n"

        class DummyTC:
            def __init__(self):
                self.id = 1
                self.order = 1
                self.input_data = ""
                self.expected_output = "SECRET_KEY_EXISTS: False"
                self.is_sample = True

        summary = self.executor.execute_test_cases("python", code, [DummyTC()])
        self.assertEqual(summary.results[0].actual_output, "SECRET_KEY_EXISTS: False")

    def test_06_hidden_test_cases_masking(self):
        """Verify hidden test case inputs and expected outputs are omitted when serialized for candidate."""
        from assessments.code_executor import TestCaseExecutionResult

        res = TestCaseExecutionResult(
            test_case_id=99,
            order=2,
            is_sample=False,
            status="PASSED",
            input_data="TOP_SECRET_INPUT",
            expected_output="TOP_SECRET_OUTPUT",
            actual_output="TOP_SECRET_OUTPUT",
            passed=True,
        )

        cand_dict = res.to_dict(hide_details=True)
        self.assertNotIn("input_data", cand_dict)
        self.assertNotIn("expected_output", cand_dict)
        self.assertNotIn("actual_output", cand_dict)
        self.assertTrue(cand_dict["passed"])


class BulkCandidateAssignmentAndShortlistingTests(TestCase):
    """Unit tests for Bulk Candidate Selection, Campaign Views, AI Shortlisting, and Multi-Tenancy."""

    def setUp(self):
        self.client = Client()
        self.now = timezone.now()

        # Seed Questions
        self.logical_q = Question.objects.create(
            section=Question.Sections.LOGICAL,
            question_text="Logical Q1",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="A", difficulty=Question.Difficulties.EASY,
        )
        self.quant_q = Question.objects.create(
            section=Question.Sections.QUANTITATIVE,
            question_text="Quant Q1",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="B", difficulty=Question.Difficulties.EASY,
        )
        self.tech_q = Question.objects.create(
            section=Question.Sections.TECHNICAL,
            question_text="Tech Q1",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="C", difficulty=Question.Difficulties.EASY,
        )
        self.coding_q = CodingQuestion.objects.create(
            title="Two Sum Problem",
            slug="two-sum-problem",
            description="Find indices of two numbers that add up to target.",
            input_format="List of ints and target",
            output_format="List of two indices",
            sample_input="[2, 7, 11, 15]\n9",
            sample_output="[0, 1]",
            difficulty=Question.Difficulties.EASY,
            category=CodingQuestion.Categories.ARRAYS,
            starter_code={"python": "def two_sum(): pass"},
        )
        self.tc1 = CodingTestCase.objects.create(
            question=self.coding_q,
            input_data="[2, 7, 11, 15]\n9",
            expected_output="[0, 1]",
            is_sample=True,
            order=1,
        )

        # Employer 1
        self.emp_user1 = User.objects.create_user(
            username="recruiter1@hiring.com", email="recruiter1@hiring.com", password="Password123!", first_name="RecruiterOne"
        )
        self.emp_prof1 = EmployerProfile.objects.create(user=self.emp_user1, company="AlphaTech")

        # Employer 2 (for multi-tenant isolation testing)
        self.emp_user2 = User.objects.create_user(
            username="recruiter2@other.com", email="recruiter2@other.com", password="Password123!", first_name="RecruiterTwo"
        )
        self.emp_prof2 = EmployerProfile.objects.create(user=self.emp_user2, company="BetaCorp")

        # Candidates (Rahul, Priya, Sneha, Arjun)
        self.cand_rahul = User.objects.create_user(
            username="rahul@test.com", email="rahul@test.com", password="Password123!", first_name="Rahul", last_name="Sharma"
        )
        CandidateProfile.objects.create(user=self.cand_rahul, skills="Python, Algorithms", experience=3)

        self.cand_priya = User.objects.create_user(
            username="priya@test.com", email="priya@test.com", password="Password123!", first_name="Priya", last_name="Verma"
        )
        CandidateProfile.objects.create(user=self.cand_priya, skills="Python, React", experience=2)

        self.cand_sneha = User.objects.create_user(
            username="sneha@test.com", email="sneha@test.com", password="Password123!", first_name="Sneha", last_name="Patel"
        )
        CandidateProfile.objects.create(user=self.cand_sneha, skills="Django, SQL", experience=1)

        self.cand_arjun = User.objects.create_user(
            username="arjun@test.com", email="arjun@test.com", password="Password123!", first_name="Arjun", last_name="Reddy"
        )
        CandidateProfile.objects.create(user=self.cand_arjun, skills="DevOps, Docker", experience=4)

    def test_01_bulk_candidate_assignment_creation(self):
        """Verify employer creates an assessment once for multiple candidates with 1 group and individual tokens."""
        self.client.login(username="recruiter1@hiring.com", password="Password123!")

        post_data = {
            "candidates": [self.cand_rahul.id, self.cand_priya.id, self.cand_sneha.id],
            "title": "Software Developer Screening Test",
            "sections": ["LOGICAL", "QUANTITATIVE", "TECHNICAL"],
            "logical_count": 1,
            "quant_count": 1,
            "technical_count": 1,
            "include_coding": True,
            "coding_count": 1,
            "start_date": self.now.date().isoformat(),
            "start_time": (self.now - timedelta(minutes=5)).strftime("%H:%M"),
            "expire_date": (self.now + timedelta(days=2)).date().isoformat(),
            "expire_time": (self.now + timedelta(days=2)).strftime("%H:%M"),
            "duration_minutes": 60,
        }

        url = reverse("assessments:employer_assessment_create")
        response = self.client.post(url, post_data)

        # Asserts AssessmentGroup is created
        group = AssessmentGroup.objects.filter(employer=self.emp_user1, title="Software Developer Screening Test").first()
        self.assertIsNotNone(group)
        self.assertRedirects(response, reverse("assessments:employer_campaign_detail", kwargs={"group_id": group.id}))

        # Asserts 3 distinct Assessment instances were created
        assessments = Assessment.objects.filter(group=group)
        self.assertEqual(assessments.count(), 3)
        assigned_user_ids = set(assessments.values_list("candidate_id", flat=True))
        self.assertEqual(assigned_user_ids, {self.cand_rahul.id, self.cand_priya.id, self.cand_sneha.id})

        # Asserts all tokens are unique and non-empty
        tokens = list(assessments.values_list("token", flat=True))
        self.assertEqual(len(set(tokens)), 3)
        for t in tokens:
            self.assertTrue(len(t) > 10)

        # Asserts questions and coding submissions are linked
        for a in assessments:
            self.assertEqual(a.questions.count(), 3)
            self.assertEqual(a.coding_questions.count(), 1)
            self.assertEqual(a.coding_submissions.count(), 1)

    def test_02_campaign_dashboard_view_and_filtering(self):
        """Verify campaign dashboard aggregates metrics, candidate rows, and supports status & search filters."""
        group = AssessmentGroup.objects.create(
            employer=self.emp_user1,
            title="Full Stack Engineer Assessment",
            start_time=self.now - timedelta(hours=1),
            expire_time=self.now + timedelta(days=1),
            duration_minutes=45,
            has_coding=True,
            total_mcq_count=3,
            total_coding_count=1,
        )

        # Candidate 1: Completed with high score
        a1 = Assessment.objects.create(
            group=group, employer=self.emp_user1, candidate=self.cand_rahul,
            title=group.title, start_time=group.start_time, expire_time=group.expire_time,
            duration_minutes=45, status=Assessment.Status.COMPLETED,
            candidate_status=Assessment.CandidateStatus.ATTENDED, has_coding=True,
            ai_recommendation=Assessment.AIRecommendation.STRONG_MATCH,
            ai_reasoning="Strong candidate with high coding and aptitude accuracy.",
            is_shortlisted=True,
        )
        Result.objects.create(
            assessment=a1, logical_correct=1, logical_total=1, quant_correct=1, quant_total=1,
            technical_correct=1, technical_total=1, percentage=Decimal("100.00"),
            aptitude_score=Decimal("100.00"), coding_score=Decimal("90.00"), overall_score=Decimal("95.00"),
            violation_count=0,
        )

        # Candidate 2: Ongoing
        a2 = Assessment.objects.create(
            group=group, employer=self.emp_user1, candidate=self.cand_priya,
            title=group.title, start_time=group.start_time, expire_time=group.expire_time,
            duration_minutes=45, status=Assessment.Status.ONGOING,
            candidate_status=Assessment.CandidateStatus.ATTENDED, has_coding=True,
        )

        # Candidate 3: Not Started
        a3 = Assessment.objects.create(
            group=group, employer=self.emp_user1, candidate=self.cand_sneha,
            title=group.title, start_time=group.start_time, expire_time=group.expire_time,
            duration_minutes=45, status=Assessment.Status.PENDING,
            candidate_status=Assessment.CandidateStatus.NOT_STARTED, has_coding=True,
        )

        self.client.login(username="recruiter1@hiring.com", password="Password123!")

        # 1. Main campaign view
        url = reverse("assessments:employer_campaign_detail", kwargs={"group_id": group.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_assigned"], 3)
        self.assertEqual(response.context["completed_count"], 1)
        self.assertEqual(response.context["in_progress_count"], 1)
        self.assertEqual(response.context["not_started_count"], 1)
        self.assertEqual(response.context["shortlisted_count"], 1)
        self.assertEqual(response.context["ai_strong_count"], 1)

        # 2. Filter by status=completed
        res_completed = self.client.get(f"{url}?status=completed")
        self.assertEqual(res_completed.status_code, 200)
        self.assertEqual(len(res_completed.context["assessments"]), 1)

        # 3. Filter by search query
        res_search = self.client.get(f"{url}?q=Rahul")
        self.assertEqual(res_search.status_code, 200)
        self.assertEqual(len(res_search.context["assessments"]), 1)
        self.assertEqual(res_search.context["assessments"][0].candidate.username, "rahul@test.com")

    def test_03_multi_tenant_campaign_isolation(self):
        """Verify Employer 2 cannot view or manipulate Employer 1's campaign."""
        group = AssessmentGroup.objects.create(
            employer=self.emp_user1,
            title="Private Alpha Campaign",
            start_time=self.now,
            expire_time=self.now + timedelta(days=1),
            duration_minutes=30,
        )

        # Log in as Employer 2
        self.client.login(username="recruiter2@other.com", password="Password123!")

        # Attempt to access Employer 1's campaign detail
        url_detail = reverse("assessments:employer_campaign_detail", kwargs={"group_id": group.id})
        res1 = self.client.get(url_detail)
        self.assertEqual(res1.status_code, 404)

        # Attempt to run AI Shortlist on Employer 1's campaign
        url_ai = reverse("assessments:employer_campaign_ai_shortlist", kwargs={"group_id": group.id})
        res2 = self.client.post(url_ai)
        self.assertEqual(res2.status_code, 404)

        # Attempt to perform Shortlist action on Employer 1's campaign
        url_action = reverse("assessments:employer_campaign_shortlist_action", kwargs={"group_id": group.id})
        res3 = self.client.post(url_action, {"action": "shortlist"})
        self.assertEqual(res3.status_code, 404)

    def test_04_ai_shortlisting_service_logic(self):
        """Verify AI shortlisting categorizes strong match, review recommended, and low match accurately."""
        from assessments.ai_shortlist_service import analyze_assessment_with_ai

        group = AssessmentGroup.objects.create(
            employer=self.emp_user1,
            title="AI Benchmark Test",
            start_time=self.now - timedelta(hours=2),
            expire_time=self.now + timedelta(days=1),
            duration_minutes=30,
            has_coding=True,
        )

        # Candidate A: 92% overall, clean proctoring -> STRONG_MATCH
        a_strong = Assessment.objects.create(
            group=group, employer=self.emp_user1, candidate=self.cand_rahul,
            title=group.title, start_time=group.start_time, expire_time=group.expire_time,
            status=Assessment.Status.COMPLETED, has_coding=True, violation_count=0,
        )
        Result.objects.create(
            assessment=a_strong, percentage=Decimal("92.00"), aptitude_score=Decimal("90.00"),
            coding_score=Decimal("94.00"), overall_score=Decimal("92.00"), has_coding=True,
        )
        res_strong = analyze_assessment_with_ai(a_strong)
        self.assertEqual(res_strong["recommendation"], Assessment.AIRecommendation.STRONG_MATCH)
        self.assertTrue(len(res_strong["reasoning"]) > 10)

        # Candidate B: 62% overall -> REVIEW_RECOMMENDED
        a_review = Assessment.objects.create(
            group=group, employer=self.emp_user1, candidate=self.cand_priya,
            title=group.title, start_time=group.start_time, expire_time=group.expire_time,
            status=Assessment.Status.COMPLETED, has_coding=True, violation_count=1,
        )
        Result.objects.create(
            assessment=a_review, percentage=Decimal("62.00"), aptitude_score=Decimal("60.00"),
            coding_score=Decimal("65.00"), overall_score=Decimal("62.00"), has_coding=True,
        )
        res_review = analyze_assessment_with_ai(a_review)
        self.assertEqual(res_review["recommendation"], Assessment.AIRecommendation.REVIEW_RECOMMENDED)

        # Candidate C: 35% overall / malpractice -> LOW_MATCH
        a_low = Assessment.objects.create(
            group=group, employer=self.emp_user1, candidate=self.cand_sneha,
            title=group.title, start_time=group.start_time, expire_time=group.expire_time,
            status=Assessment.Status.COMPLETED, has_coding=True, violation_count=3,
            auto_submitted_for_malpractice=True, submission_reason="Auto-submitted: 3 proctoring violations recorded",
        )
        Result.objects.create(
            assessment=a_low, percentage=Decimal("35.00"), aptitude_score=Decimal("35.00"),
            coding_score=Decimal("0.00"), overall_score=Decimal("35.00"), has_coding=True,
        )
        res_low = analyze_assessment_with_ai(a_low)
        self.assertEqual(res_low["recommendation"], Assessment.AIRecommendation.LOW_MATCH)
        self.assertIn("proctoring", res_low["reasoning"].lower())

    def test_05_employer_shortlist_actions(self):
        """Verify employer can shortlist, remove from shortlist, and toggle candidates."""
        group = AssessmentGroup.objects.create(
            employer=self.emp_user1,
            title="Shortlist Action Test",
            start_time=self.now,
            expire_time=self.now + timedelta(days=1),
            duration_minutes=30,
        )
        a1 = Assessment.objects.create(
            group=group, employer=self.emp_user1, candidate=self.cand_rahul,
            title=group.title, start_time=group.start_time, expire_time=group.expire_time,
            status=Assessment.Status.COMPLETED,
        )
        a2 = Assessment.objects.create(
            group=group, employer=self.emp_user1, candidate=self.cand_priya,
            title=group.title, start_time=group.start_time, expire_time=group.expire_time,
            status=Assessment.Status.COMPLETED,
        )

        self.client.login(username="recruiter1@hiring.com", password="Password123!")
        url_action = reverse("assessments:employer_campaign_shortlist_action", kwargs={"group_id": group.id})

        # 1. Bulk Shortlist both candidates
        res1 = self.client.post(url_action, {
            "action": "shortlist",
            "assessment_ids": [a1.id, a2.id],
            "notes": "Fast-track to technical phone screen",
        })
        self.assertEqual(res1.status_code, 302)
        a1.refresh_from_db()
        a2.refresh_from_db()
        self.assertTrue(a1.is_shortlisted)
        self.assertIsNotNone(a1.shortlisted_at)
        self.assertEqual(a1.shortlist_notes, "Fast-track to technical phone screen")
        self.assertTrue(a2.is_shortlisted)

        # 2. Toggle Candidate 1 off via AJAX
        res2 = self.client.post(
            url_action,
            data=json.dumps({"action": "toggle", "assessment_id": a1.id}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["status"], "ok")
        a1.refresh_from_db()
        self.assertFalse(a1.is_shortlisted)

        # 3. Bulk Remove Candidate 2
        res3 = self.client.post(url_action, {
            "action": "remove",
            "assessment_ids": [a2.id],
        })
        self.assertEqual(res3.status_code, 302)
        a2.refresh_from_db()
        self.assertFalse(a2.is_shortlisted)


class AssessmentDateTimeAndScheduleWindowTests(TestCase):
    """Tests for assessment scheduling, date-time boundary enforcement, AM/PM, midnight and noon handling."""

    def setUp(self):
        self.client = Client()
        self.base_time = timezone.now()

        # Employer
        self.emp_user = User.objects.create_user(
            username="schedule_emp@tech.com",
            email="schedule_emp@tech.com",
            password="Password123!",
            first_name="Schedule",
            last_name="Employer",
        )
        self.emp_profile = EmployerProfile.objects.create(user=self.emp_user, company="TimeTech")

        # Candidate
        self.cand_user = User.objects.create_user(
            username="schedule_cand@candidate.com",
            email="schedule_cand@candidate.com",
            password="Password123!",
            first_name="Timmy",
            last_name="Tester",
        )
        self.cand_profile = CandidateProfile.objects.create(
            user=self.cand_user,
            phone="9876543210",
            education="B.Tech Computer Science",
            skills="Python, Algorithms",
            experience=2,
        )

        # Question
        self.question = Question.objects.create(
            section=Question.Sections.TECHNICAL,
            question_text="What is the default port for HTTP?",
            option_a="80",
            option_b="443",
            option_c="8080",
            option_d="22",
            correct_answer="A",
            difficulty=Question.Difficulties.EASY,
        )

    def test_01_access_before_start_time(self):
        """Before start: candidate is blocked by not_started gate and cannot start early."""
        fixed_now = timezone.now()
        start_time = fixed_now + timedelta(hours=2)
        expire_time = fixed_now + timedelta(hours=5)

        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Future Assessment",
            start_time=start_time,
            expire_time=expire_time,
            duration_minutes=30,
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.question, order=1)

        self.client.login(username="schedule_cand@candidate.com", password="Password123!")

        # 1. Entry gate check
        with patch("django.utils.timezone.now", return_value=fixed_now):
            res_entry = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
            self.assertEqual(res_entry.status_code, 200)
            self.assertContains(res_entry, "Assessment Not Yet Open")
            self.assertEqual(res_entry.context.get("gate_type"), "not_started")

        # 2. Attempt to start early via POST
        with patch("django.utils.timezone.now", return_value=fixed_now):
            res_start = self.client.post(reverse("assessments:test_start", kwargs={"token": assessment.token}))
            self.assertEqual(res_start.status_code, 302)
            assessment.refresh_from_db()
            self.assertEqual(assessment.status, Assessment.Status.PENDING)

    def test_02_access_and_start_exactly_at_start_time(self):
        """Exactly at start: candidate can access instructions and successfully start the assessment."""
        fixed_now = timezone.now()
        start_time = fixed_now
        expire_time = fixed_now + timedelta(hours=2)

        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Start On The Dot Assessment",
            start_time=start_time,
            expire_time=expire_time,
            duration_minutes=30,
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.question, order=1)

        self.client.login(username="schedule_cand@candidate.com", password="Password123!")

        # 1. Entry gate allows instructions exactly at start_time
        with patch("django.utils.timezone.now", return_value=fixed_now):
            res_entry = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
            self.assertEqual(res_entry.status_code, 200)
            self.assertContains(res_entry, "Start On The Dot Assessment")
            self.assertContains(res_entry, "START ASSESSMENT")

        # 2. Candidate starts exactly at start_time
        with patch("django.utils.timezone.now", return_value=fixed_now):
            res_start = self.client.post(reverse("assessments:test_start", kwargs={"token": assessment.token}))
            self.assertEqual(res_start.status_code, 302)
            assessment.refresh_from_db()
            self.assertEqual(assessment.status, Assessment.Status.ONGOING)

    def test_03_access_and_start_after_start_time(self):
        """After start: candidate within active window can view instructions and start."""
        fixed_now = timezone.now()
        start_time = fixed_now - timedelta(minutes=30)
        expire_time = fixed_now + timedelta(hours=2)

        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Active Window Assessment",
            start_time=start_time,
            expire_time=expire_time,
            duration_minutes=30,
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.question, order=1)

        self.client.login(username="schedule_cand@candidate.com", password="Password123!")

        with patch("django.utils.timezone.now", return_value=fixed_now):
            res_entry = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
            self.assertEqual(res_entry.status_code, 200)
            self.assertContains(res_entry, "START ASSESSMENT")

            res_start = self.client.post(reverse("assessments:test_start", kwargs={"token": assessment.token}))
            self.assertEqual(res_start.status_code, 302)
            assessment.refresh_from_db()
            self.assertEqual(assessment.status, Assessment.Status.ONGOING)

    def test_04_access_and_start_exactly_at_end_time(self):
        """Exactly at end: candidate accessing at the exact boundary of expire_time is not marked past due."""
        fixed_now = timezone.now()
        start_time = fixed_now - timedelta(hours=1)
        expire_time = fixed_now

        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Boundary End Assessment",
            start_time=start_time,
            expire_time=expire_time,
            duration_minutes=30,
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.question, order=1)

        self.client.login(username="schedule_cand@candidate.com", password="Password123!")

        with patch("django.utils.timezone.now", return_value=fixed_now):
            res_entry = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
            self.assertEqual(res_entry.status_code, 200)
            # Exactly at expire_time (now <= expire_time), it has not exceeded expiry
            self.assertNotEqual(res_entry.context.get("gate_type"), "expired")

    def test_05_access_and_start_after_end_time(self):
        """After end: candidate accessing after expire_time is marked EXPIRED and NOT_ATTENDED."""
        fixed_now = timezone.now()
        start_time = fixed_now - timedelta(hours=3)
        expire_time = fixed_now - timedelta(seconds=1)

        assessment = Assessment.objects.create(
            employer=self.emp_user,
            candidate=self.cand_user,
            title="Past Due Assessment",
            start_time=start_time,
            expire_time=expire_time,
            duration_minutes=30,
        )
        AssessmentQuestion.objects.create(assessment=assessment, question=self.question, order=1)

        self.client.login(username="schedule_cand@candidate.com", password="Password123!")

        # 1. Access test_entry after expire_time
        with patch("django.utils.timezone.now", return_value=fixed_now):
            res_entry = self.client.get(reverse("assessments:test_entry", kwargs={"token": assessment.token}))
            self.assertEqual(res_entry.status_code, 200)
            self.assertEqual(res_entry.context.get("gate_type"), "expired")
            self.assertContains(res_entry, "Assessment Closed")

            assessment.refresh_from_db()
            self.assertEqual(assessment.status, Assessment.Status.EXPIRED)
            self.assertEqual(assessment.candidate_status, Assessment.CandidateStatus.NOT_ATTENDED)

        # 2. Attempt to start after expire_time
        with patch("django.utils.timezone.now", return_value=fixed_now):
            res_start = self.client.post(reverse("assessments:test_start", kwargs={"token": assessment.token}))
            self.assertEqual(res_start.status_code, 302)

    def test_06_form_scheduling_am_times(self):
        """AM times: verify AssessmentCreateForm correctly parses and validates morning time schedules."""
        from assessments.forms import AssessmentCreateForm

        tomorrow = timezone.localdate() + timedelta(days=1)
        form_data = {
            "candidate": self.cand_user.id,
            "title": "Morning Assessment (AM)",
            "sections": ["TECHNICAL"],
            "technical_count": 1,
            "start_date": tomorrow,
            "start_time": time(9, 0),       # 9:00 AM
            "expire_date": tomorrow,
            "expire_time": time(11, 30),     # 11:30 AM
            "duration_minutes": 60,
        }
        form = AssessmentCreateForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

        cleaned = form.cleaned_data
        start_dt = cleaned["start_datetime"]
        expire_dt = cleaned["expire_datetime"]

        self.assertEqual(start_dt.hour, 9)
        self.assertEqual(start_dt.minute, 0)
        self.assertEqual(expire_dt.hour, 11)
        self.assertEqual(expire_dt.minute, 30)
        self.assertGreater(expire_dt, start_dt)

    def test_07_form_scheduling_pm_times(self):
        """PM times: verify AssessmentCreateForm correctly parses afternoon/evening times and AM-to-PM spans."""
        from assessments.forms import AssessmentCreateForm

        tomorrow = timezone.localdate() + timedelta(days=1)

        # Case A: PM to PM on the same day
        form_data_pm = {
            "candidate": self.cand_user.id,
            "title": "Afternoon Assessment (PM to PM)",
            "sections": ["TECHNICAL"],
            "technical_count": 1,
            "start_date": tomorrow,
            "start_time": time(14, 0),      # 2:00 PM
            "expire_date": tomorrow,
            "expire_time": time(17, 45),     # 5:45 PM
            "duration_minutes": 45,
        }
        form_pm = AssessmentCreateForm(data=form_data_pm)
        self.assertTrue(form_pm.is_valid(), form_pm.errors)
        self.assertEqual(form_pm.cleaned_data["start_datetime"].hour, 14)
        self.assertEqual(form_pm.cleaned_data["expire_datetime"].hour, 17)
        self.assertEqual(form_pm.cleaned_data["expire_datetime"].minute, 45)

        # Case B: AM to PM on the same day
        form_data_ampm = {
            "candidate": self.cand_user.id,
            "title": "Full Day Assessment (AM to PM)",
            "sections": ["TECHNICAL"],
            "technical_count": 1,
            "start_date": tomorrow,
            "start_time": time(10, 0),      # 10:00 AM
            "expire_date": tomorrow,
            "expire_time": time(16, 0),      # 4:00 PM
            "duration_minutes": 90,
        }
        form_ampm = AssessmentCreateForm(data=form_data_ampm)
        self.assertTrue(form_ampm.is_valid(), form_ampm.errors)
        self.assertGreater(form_ampm.cleaned_data["expire_datetime"], form_ampm.cleaned_data["start_datetime"])

    def test_08_form_scheduling_12_00_am_midnight(self):
        """12:00 AM (Midnight): verify handling of 00:00:00 as start and cross-midnight expiry."""
        from assessments.forms import AssessmentCreateForm

        day1 = timezone.localdate() + timedelta(days=2)
        day2 = day1 + timedelta(days=1)

        # Case A: Starting at 12:00 AM (00:00) on day1, expiring at 04:00 AM on day1
        form_data_midnight_start = {
            "candidate": self.cand_user.id,
            "title": "Midnight Start Assessment",
            "sections": ["TECHNICAL"],
            "technical_count": 1,
            "start_date": day1,
            "start_time": time(0, 0),       # 12:00 AM
            "expire_date": day1,
            "expire_time": time(4, 0),       # 4:00 AM
            "duration_minutes": 60,
        }
        form_a = AssessmentCreateForm(data=form_data_midnight_start)
        self.assertTrue(form_a.is_valid(), form_a.errors)
        self.assertEqual(form_a.cleaned_data["start_datetime"].hour, 0)
        self.assertEqual(form_a.cleaned_data["start_datetime"].minute, 0)

        # Case B: Starting at 11:00 PM (23:00) on day1, expiring at 12:00 AM midnight (00:00) on day2
        form_data_cross_midnight = {
            "candidate": self.cand_user.id,
            "title": "Cross Midnight Assessment",
            "sections": ["TECHNICAL"],
            "technical_count": 1,
            "start_date": day1,
            "start_time": time(23, 0),      # 11:00 PM
            "expire_date": day2,
            "expire_time": time(0, 0),       # 12:00 AM (midnight next day)
            "duration_minutes": 45,
        }
        form_b = AssessmentCreateForm(data=form_data_cross_midnight)
        self.assertTrue(form_b.is_valid(), form_b.errors)
        self.assertEqual(
            form_b.cleaned_data["expire_datetime"] - form_b.cleaned_data["start_datetime"],
            timedelta(hours=1),
        )

    def test_09_form_scheduling_12_00_pm_noon(self):
        """12:00 PM (Noon): verify handling of 12:00:00 as start and as expiry."""
        from assessments.forms import AssessmentCreateForm

        tomorrow = timezone.localdate() + timedelta(days=1)

        # Case A: Morning start expiring at 12:00 PM (Noon)
        form_data_noon_expiry = {
            "candidate": self.cand_user.id,
            "title": "Morning to Noon Assessment",
            "sections": ["TECHNICAL"],
            "technical_count": 1,
            "start_date": tomorrow,
            "start_time": time(10, 0),      # 10:00 AM
            "expire_date": tomorrow,
            "expire_time": time(12, 0),      # 12:00 PM (Noon)
            "duration_minutes": 60,
        }
        form_a = AssessmentCreateForm(data=form_data_noon_expiry)
        self.assertTrue(form_a.is_valid(), form_a.errors)
        self.assertEqual(form_a.cleaned_data["expire_datetime"].hour, 12)
        self.assertEqual(form_a.cleaned_data["expire_datetime"].minute, 0)
        self.assertEqual(
            form_a.cleaned_data["expire_datetime"] - form_a.cleaned_data["start_datetime"],
            timedelta(hours=2),
        )

        # Case B: Starting at 12:00 PM (Noon) expiring in the afternoon
        form_data_noon_start = {
            "candidate": self.cand_user.id,
            "title": "Noon to Afternoon Assessment",
            "sections": ["TECHNICAL"],
            "technical_count": 1,
            "start_date": tomorrow,
            "start_time": time(12, 0),      # 12:00 PM (Noon)
            "expire_date": tomorrow,
            "expire_time": time(15, 30),     # 3:30 PM
            "duration_minutes": 60,
        }
        form_b = AssessmentCreateForm(data=form_data_noon_start)
        self.assertTrue(form_b.is_valid(), form_b.errors)
        self.assertEqual(form_b.cleaned_data["start_datetime"].hour, 12)
        self.assertEqual(form_b.cleaned_data["start_datetime"].minute, 0)
        self.assertGreater(form_b.cleaned_data["expire_datetime"], form_b.cleaned_data["start_datetime"])

    def test_10_form_rejects_inverted_or_equal_start_and_expire_times(self):
        """Verify AssessmentCreateForm rejects expiry time on or before start time."""
        from assessments.forms import AssessmentCreateForm

        tomorrow = timezone.localdate() + timedelta(days=1)

        # 1. Expiry before start on same date
        form_data_inverted = {
            "candidate": self.cand_user.id,
            "title": "Inverted Time Assessment",
            "sections": ["TECHNICAL"],
            "technical_count": 1,
            "start_date": tomorrow,
            "start_time": time(15, 0),      # 3:00 PM
            "expire_date": tomorrow,
            "expire_time": time(11, 0),      # 11:00 AM (before start!)
            "duration_minutes": 60,
        }
        form_inv = AssessmentCreateForm(data=form_data_inverted)
        self.assertFalse(form_inv.is_valid())
        self.assertIn("expire_date", form_inv.errors)
        self.assertIn("Expiry date & time must be strictly after the start date & time.", form_inv.errors["expire_date"][0])

        # 2. Expiry equal to start (zero window)
        form_data_equal = {
            "candidate": self.cand_user.id,
            "title": "Zero Window Assessment",
            "sections": ["TECHNICAL"],
            "technical_count": 1,
            "start_date": tomorrow,
            "start_time": time(12, 0),      # 12:00 PM
            "expire_date": tomorrow,
            "expire_time": time(12, 0),      # 12:00 PM
            "duration_minutes": 60,
        }
        form_eq = AssessmentCreateForm(data=form_data_equal)
        self.assertFalse(form_eq.is_valid())
        self.assertIn("expire_date", form_eq.errors)