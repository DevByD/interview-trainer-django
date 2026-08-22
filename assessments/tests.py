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
        self.assertContains(expired_res, "Assessment Expired")
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