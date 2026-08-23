"""E2E Test Configuration & Playwright Fixtures.

Configures isolated test environments, live server instances, and browser contexts
with simulated media devices for proctoring verification.
"""

import os

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import pytest
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
from playwright.sync_api import sync_playwright

from accounts.models import CandidateProfile, EmployerProfile
from assessments.models import (
    Answer,
    Assessment,
    AssessmentCodingQuestion,
    AssessmentQuestion,
    CodingQuestion,
    CodingSubmission,
    CodingTestCase,
    Question,
)


@pytest.fixture(scope="session")
def playwright_instance():
    """Session-scoped Playwright instance."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser_type(playwright_instance):
    return playwright_instance.chromium


@pytest.fixture(scope="session")
def browser(browser_type):
    """Chromium browser instance launched with simulated camera and microphone devices."""
    b = browser_type.launch(
        headless=True,
        args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    yield b
    b.close()


@pytest.fixture
def browser_context(browser):
    """Fresh browser context with camera & microphone permissions granted."""
    context = browser.new_context(
        permissions=["camera", "microphone"],
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    context.add_init_script("window.__fullscreenOverride = true;")
    yield context
    context.close()


@pytest.fixture
def browser_context_denied(browser):
    """Fresh browser context with media permissions denied/restricted."""
    context = browser.new_context(
        permissions=[],
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    yield context
    context.close()


@pytest.fixture
def test_setup_data(db):
    """Seed minimal test users, questions, coding challenges, and assessments."""
    now = timezone.now()

    # 1. Employer User & Profile
    employer_user = User.objects.create_user(
        username="e2e_employer@testcorp.com",
        email="e2e_employer@testcorp.com",
        password="TestPassword123!",
        first_name="Test",
        last_name="Employer",
    )
    employer_profile = EmployerProfile.objects.create(
        user=employer_user,
        company="Acme Corp",
    )

    # 2. Candidate User & Profile
    candidate_user = User.objects.create_user(
        username="e2e_candidate@test.com",
        email="e2e_candidate@test.com",
        password="TestPassword123!",
        first_name="John",
        last_name="Candidate",
    )
    candidate_profile = CandidateProfile.objects.create(
        user=candidate_user,
        phone="5551234567",
        education="B.S. in Computer Science",
        skills="Python, Django, React, Algorithms",
        profile_completed=True,
    )

    # 3. Aptitude Questions
    q1 = Question.objects.create(
        section=Question.Sections.LOGICAL,
        question_text="What is the next number in sequence: 3, 6, 12, 24, ?",
        option_a="36",
        option_b="48",
        option_c="42",
        option_d="30",
        correct_answer="B",
        difficulty=Question.Difficulties.EASY,
    )

    q2 = Question.objects.create(
        section=Question.Sections.TECHNICAL,
        question_text="What is the time complexity of binary search on a sorted array?",
        option_a="O(n)",
        option_b="O(n log n)",
        option_c="O(log n)",
        option_d="O(1)",
        correct_answer="C",
        difficulty=Question.Difficulties.EASY,
    )

    q3 = Question.objects.create(
        section=Question.Sections.QUANTITATIVE,
        question_text="If a train travels 120 km in 2 hours, what is its speed in km/h?",
        option_a="50",
        option_b="60",
        option_c="70",
        option_d="80",
        correct_answer="B",
        difficulty=Question.Difficulties.EASY,
    )

    # 4. Coding Question with Test Cases
    cq = CodingQuestion.objects.create(
        title="Two Sum Problem",
        slug="e2e-two-sum-problem",
        category=CodingQuestion.Categories.ARRAYS,
        description="Given an array of integers and a target, return indices of two numbers that add up to target.",
        input_format="First line: space-separated integers. Second line: target integer.",
        output_format="Space-separated indices.",
        constraints="2 <= nums.length <= 10^4",
        sample_input="2 7 11 15\n9",
        sample_output="0 1",
        explanation="2 + 7 = 9, so indices are 0 1.",
        difficulty=Question.Difficulties.EASY,
        starter_code={
            "python": "# Write your Python solution here\n",
            "java": "// Write your Java solution here\n",
            "cpp": "// Write your C++ solution here\n",
            "javascript": "// Write your JS solution here\n",
        },
        max_score=100,
    )

    CodingTestCase.objects.create(
        question=cq,
        input_data="2 7 11 15\n9",
        expected_output="0 1",
        is_sample=True,
        order=1,
    )
    CodingTestCase.objects.create(
        question=cq,
        input_data="3 2 4\n6",
        expected_output="1 2",
        is_sample=True,
        order=2,
    )
    CodingTestCase.objects.create(
        question=cq,
        input_data="3 3\n6",
        expected_output="0 1",
        is_sample=False,
        order=3,
    )

    # 5. Pending Assessment
    assessment = Assessment.objects.create(
        employer=employer_user,
        candidate=candidate_user,
        title="Software Engineering Assessment",
        start_time=now - timedelta(minutes=5),
        expire_time=now + timedelta(hours=2),
        duration_minutes=45,
        status=Assessment.Status.PENDING,
        candidate_status=Assessment.CandidateStatus.NOT_STARTED,
        has_coding=True,
        max_violations=3,
    )

    AssessmentQuestion.objects.create(assessment=assessment, question=q1, order=1)
    AssessmentQuestion.objects.create(assessment=assessment, question=q2, order=2)
    AssessmentQuestion.objects.create(assessment=assessment, question=q3, order=3)
    AssessmentCodingQuestion.objects.create(assessment=assessment, question=cq, order=1)

    CodingSubmission.objects.create(
        assessment=assessment,
        question=cq,
        language="python",
        source_code="",
        total_test_cases=3,
    )

    return {
        "employer_user": employer_user,
        "employer_profile": employer_profile,
        "candidate_user": candidate_user,
        "candidate_profile": candidate_profile,
        "assessment": assessment,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "cq": cq,
    }
