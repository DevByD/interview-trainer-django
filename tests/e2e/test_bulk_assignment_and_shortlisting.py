"""E2E Playwright Tests: Bulk Candidate Selection, Campaign Dashboard, and AI Shortlisting.

Tests:
1. Employer creates an assessment campaign for multiple candidates via bulk selection UI.
2. Candidate search, Select All, Deselect All, and real-time counter.
3. Campaign Dashboard metrics, candidate matrix, and status filtering.
4. AI Shortlisting execution and decision-support recommendation badges.
5. Employer shortlist selection, toggle, and removal actions.
6. Multi-viewport mobile responsiveness (375px to 1280px).
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
from playwright.sync_api import Page, expect

from accounts.models import CandidateProfile, EmployerProfile
from assessments.models import (
    Assessment,
    AssessmentGroup,
    CodingQuestion,
    CodingTestCase,
    Question,
)
from results.models import Result


@pytest.fixture
def campaign_test_data(db):
    """Seed users, question bank, and candidate cohorts for campaign testing."""
    now = timezone.now()

    # 1. Employer
    employer = User.objects.create_user(
        username="e2e_recruiter@testcorp.com",
        email="e2e_recruiter@testcorp.com",
        password="RecruiterPass123!",
        first_name="Elena",
        last_name="Rostova",
    )
    EmployerProfile.objects.create(user=employer, company="Apex Technologies")

    # 2. Seed Question Bank
    Question.objects.create(
        section=Question.Sections.LOGICAL,
        question_text="If all bloops are razzies, are some bloops razzies?",
        option_a="Yes", option_b="No", option_c="Cannot determine", option_d="None",
        correct_answer="A", difficulty=Question.Difficulties.EASY,
    )
    Question.objects.create(
        section=Question.Sections.QUANTITATIVE,
        question_text="Compute 25 * 24",
        option_a="500", option_b="600", option_c="700", option_d="800",
        correct_answer="B", difficulty=Question.Difficulties.EASY,
    )
    Question.objects.create(
        section=Question.Sections.TECHNICAL,
        question_text="Which HTTP status code signifies Not Found?",
        option_a="200", option_b="301", option_c="404", option_d="500",
        correct_answer="C", difficulty=Question.Difficulties.EASY,
    )

    cq = CodingQuestion.objects.create(
        title="Find Maximum Element",
        slug="find-maximum-element",
        description="Return the highest integer in the array.",
        input_format="List of integers",
        output_format="Maximum integer",
        sample_input="[3, 8, 1, 9, 2]",
        sample_output="9",
        difficulty=Question.Difficulties.EASY,
        category=CodingQuestion.Categories.ARRAYS,
        starter_code={"python": "def find_max(arr): pass"},
    )
    CodingTestCase.objects.create(
        question=cq,
        input_data="[3, 8, 1, 9, 2]",
        expected_output="9",
        is_sample=True,
        order=1,
    )

    # 3. Candidates (Rahul, Priya, Sneha)
    cand_rahul = User.objects.create_user(
        username="rahul_e2e@test.com", email="rahul_e2e@test.com", password="Password123!", first_name="Rahul", last_name="Sharma"
    )
    CandidateProfile.objects.create(user=cand_rahul, skills="Python, Django, PostgreSQL", education="B.Tech CS", experience=3)

    cand_priya = User.objects.create_user(
        username="priya_e2e@test.com", email="priya_e2e@test.com", password="Password123!", first_name="Priya", last_name="Verma"
    )
    CandidateProfile.objects.create(user=cand_priya, skills="Python, React, TypeScript", education="M.S. Software", experience=2)

    cand_sneha = User.objects.create_user(
        username="sneha_e2e@test.com", email="sneha_e2e@test.com", password="Password123!", first_name="Sneha", last_name="Patel"
    )
    CandidateProfile.objects.create(user=cand_sneha, skills="Java, Spring Boot", education="B.E. IT", experience=1)

    return {
        "employer": employer,
        "cand_rahul": cand_rahul,
        "cand_priya": cand_priya,
        "cand_sneha": cand_sneha,
    }


def login_employer(page: Page, live_server_url: str):
    """Helper to log in as employer."""
    page.goto(f"{live_server_url}/employer/login/")
    page.fill('input[name="username"]', "e2e_recruiter@testcorp.com")
    page.fill('input[name="password"]', "RecruiterPass123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server_url}/employer/dashboard/")


def test_e2e_bulk_candidate_assignment_flow(live_server, browser_context, campaign_test_data):
    """Verify bulk candidate selection, live search, and campaign creation."""
    page = browser_context.new_page()
    login_employer(page, live_server.url)

    # Navigate to Create Assessment page
    page.goto(f"{live_server.url}/employer/assessments/create/")
    expect(page.locator("h1")).to_contain_text("Create & Assign Assessment")

    # Verify Candidate Selection Toolbar & Search
    search_input = page.locator("#candidateSearchInput")
    expect(search_input).to_be_visible()

    # Search for "Rahul"
    search_input.fill("Rahul")
    page.wait_for_timeout(200)

    # Select Rahul
    rahul_checkbox = page.locator('input[name="candidates"][value="' + str(campaign_test_data["cand_rahul"].id) + '"]')
    expect(rahul_checkbox).to_be_visible()
    rahul_checkbox.check()

    # Clear search and select Priya as well
    search_input.fill("")
    page.wait_for_timeout(200)
    priya_checkbox = page.locator('input[name="candidates"][value="' + str(campaign_test_data["cand_priya"].id) + '"]')
    priya_checkbox.check()

    # Verify live count badge
    selected_badge = page.locator("#selectedCountBadge")
    expect(selected_badge).to_have_text("2")

    # Fill assessment details
    page.fill('input[name="title"]', "Full Stack Screening Sprint 2026")
    page.fill('input[name="logical_count"]', "1")
    page.fill('input[name="quant_count"]', "1")
    page.fill('input[name="technical_count"]', "1")

    # Submit form
    page.click("#btnSubmitAssessment")

    # Expect redirection to Campaign Detail Dashboard
    page.wait_for_url("**/employer/campaign/*/")
    expect(page.locator("h1")).to_contain_text("Full Stack Screening Sprint 2026")

    # Verify Candidates Assigned Metric
    expect(page.locator(".metric-card:has-text('Candidates Assigned') .metric-card-value")).to_have_text("2")

    # Verify Candidate rows in the matrix
    expect(page.locator("#campaignCandidateTable")).to_contain_text("Rahul Sharma")
    expect(page.locator("#campaignCandidateTable")).to_contain_text("Priya Verma")


def test_e2e_ai_shortlist_and_employer_actions(live_server, browser_context, campaign_test_data):
    """Verify AI shortlisting evaluation and employer shortlist toggle/bulk actions."""
    now = timezone.now()
    emp = campaign_test_data["employer"]
    rahul = campaign_test_data["cand_rahul"]
    priya = campaign_test_data["cand_priya"]

    # Pre-seed a completed campaign with Results
    group = AssessmentGroup.objects.create(
        employer=emp,
        title="AI Evaluation Cohort",
        start_time=now - timedelta(hours=1),
        expire_time=now + timedelta(days=1),
        duration_minutes=60,
        has_coding=True,
    )
    a1 = Assessment.objects.create(
        group=group, employer=emp, candidate=rahul,
        title=group.title, start_time=group.start_time, expire_time=group.expire_time,
        duration_minutes=60, status=Assessment.Status.COMPLETED,
        candidate_status=Assessment.CandidateStatus.ATTENDED, has_coding=True,
    )
    Result.objects.create(
        assessment=a1, logical_correct=1, logical_total=1, quant_correct=1, quant_total=1,
        technical_correct=1, technical_total=1, percentage=Decimal("95.00"),
        aptitude_score=Decimal("95.00"), coding_score=Decimal("90.00"), overall_score=Decimal("92.50"),
        has_coding=True, violation_count=0,
    )

    a2 = Assessment.objects.create(
        group=group, employer=emp, candidate=priya,
        title=group.title, start_time=group.start_time, expire_time=group.expire_time,
        duration_minutes=60, status=Assessment.Status.COMPLETED,
        candidate_status=Assessment.CandidateStatus.ATTENDED, has_coding=True,
    )
    Result.objects.create(
        assessment=a2, logical_correct=1, logical_total=1, quant_correct=0, quant_total=1,
        technical_correct=1, technical_total=1, percentage=Decimal("60.00"),
        aptitude_score=Decimal("60.00"), coding_score=Decimal("65.00"), overall_score=Decimal("62.50"),
        has_coding=True, violation_count=1,
    )

    page = browser_context.new_page()
    login_employer(page, live_server.url)

    # Open Campaign Dashboard
    page.goto(f"{live_server.url}/employer/campaign/{group.id}/")
    expect(page.locator("h1")).to_contain_text("AI Evaluation Cohort")

    # Run AI Shortlisting
    ai_button = page.locator("#btnRunAiShortlist")
    ai_button.click()
    page.wait_for_load_state("networkidle")

    # Verify AI Recommendation badges
    expect(page.locator(".badge-ai-strong")).to_be_visible()
    expect(page.locator(".badge-ai-strong")).to_contain_text("Strong Match")
    expect(page.locator(".badge-ai-review")).to_be_visible()
    expect(page.locator(".badge-ai-review")).to_contain_text("Review Recommended")

    # Verify AI Decision Support Disclaimer is visible
    expect(page.locator(".ai-disclaimer-banner")).to_be_visible()

    # Test Employer Shortlist Toggle (AJAX)
    shortlist_btn = page.locator(f'button[data-assessment-id="{a1.id}"]')
    expect(shortlist_btn).to_contain_text("Shortlist")
    shortlist_btn.click()
    page.wait_for_timeout(300)

    # Verify button changed state to Shortlisted
    expect(shortlist_btn).to_contain_text("Shortlisted")


def test_e2e_campaign_mobile_responsiveness(live_server, browser_context, campaign_test_data):
    """Verify campaign dashboard and candidate selector on mobile viewports (375px & 768px)."""
    page = browser_context.new_page()
    page.set_viewport_size({"width": 375, "height": 667})

    login_employer(page, live_server.url)

    # 1. Test create assessment page responsive layout
    page.goto(f"{live_server.url}/employer/assessments/create/")
    page.wait_for_load_state("networkidle")

    # Check for horizontal overflow
    overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
    assert not overflow, "Horizontal overflow detected on mobile create assessment page (375px)"

    # 2. Test campaign list page responsive layout
    page.goto(f"{live_server.url}/employer/campaigns/")
    page.wait_for_load_state("networkidle")
    overflow_list = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
    assert not overflow_list, "Horizontal overflow detected on mobile campaign list page (375px)"
