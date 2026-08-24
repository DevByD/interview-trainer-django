"""End-to-End Test Suite: Complete Assessment Flow.

Tests:
1. Candidate Authentication
2. Secure Test Entry via Token
3. Instructions & System Check Device Verification (Camera, Mic, Fullscreen)
4. Assessment Start & Question Rendering (Ensuring NO false auto-submission)
5. Answer Selection, Next/Previous Navigation, & Client-Server Answer Persistence
6. Final Test Submission & Instant Auto-Grading
7. Candidate Result View Verification
8. Employer Dashboard & Result Verification
"""

import pytest
import re
from playwright.sync_api import expect
from assessments.models import Assessment


@pytest.mark.django_db(transaction=True)
def test_full_mcq_assessment_lifecycle(live_server, browser_context, test_setup_data):
    """Verify complete end-to-end flow from candidate login to employer result inspection."""
    candidate_user = test_setup_data["candidate_user"]
    assessment = test_setup_data["assessment"]
    employer_user = test_setup_data["employer_user"]

    # Set has_coding to False for dedicated MCQ assessment flow test
    assessment.has_coding = False
    assessment.save()

    page = browser_context.new_page()

    # Step 1: Candidate Login
    page.goto(f"{live_server.url}/candidate/login/")
    expect(page.locator("h2, h1").first).to_contain_text(re.compile(r"Login|Sign In|Candidate", re.I))

    page.fill('input[name="username"]', candidate_user.username)
    page.fill('input[name="password"]', "TestPassword123!")
    page.click('button[type="submit"]')

    # Verify candidate landed on candidate dashboard
    page.wait_for_url(f"{live_server.url}/candidate/dashboard/")
    expect(page.locator(".brand").first).to_be_visible()

    # Step 2: Open Assessment Test Entry via Secure Token
    test_url = f"{live_server.url}/test/{assessment.token}/"
    page.goto(test_url)

    # Step 3: Instructions & System Readiness Check
    expect(page.locator("h1")).to_contain_text(assessment.title)
    expect(page.locator(".system-check-card")).to_be_visible()

    # Start button must initially be disabled
    start_btn = page.locator("#btnStartAssessment")
    expect(start_btn).to_be_disabled()

    # Click "Test Camera & Microphone"
    test_media_btn = page.locator("#btnTestMedia")
    test_media_btn.click()

    # Verify Camera and Mic rows update to Ready
    expect(page.locator("#badgeCamera")).to_have_text("Ready", timeout=8000)
    expect(page.locator("#badgeMic")).to_have_text("Ready", timeout=8000)

    # Set fullscreen override for headless environment
    page.evaluate("() => { window.__fullscreenOverride = true; if (typeof updateCheckStatusUI === 'function') { updateCheckStatusUI(); } }")

    # Start button should now be enabled and active
    expect(start_btn).to_be_enabled(timeout=5000)
    expect(page.locator("#summaryText")).to_have_text("ALL CHECKS PASSED")

    # Step 4: Click START ASSESSMENT NOW
    start_btn.click()

    # Step 5: Verify Candidate Enters Test & Question 1 is visible (NOT auto-submitted)
    expect(page.locator(".test-header-bar")).to_be_visible(timeout=8000)
    expect(page.locator("#timerDisplay")).to_be_visible()
    
    # Verify Question 1 is active and visible
    q1_pane = page.locator("#question-pane-1")
    expect(q1_pane).to_be_visible()
    expect(q1_pane.locator(".question-text")).to_contain_text("What is the next number in sequence")

    # Step 6: Select Answer Option on Question 1 (Option B = "48")
    opt_b = q1_pane.locator('.option-item[data-opt="B"]')
    opt_b.click()
    expect(opt_b).to_have_class(re.compile(r"selected"))
    expect(page.locator("#palette-btn-1")).to_have_class(re.compile(r"answered"))

    # Step 7: Click Next to move to Question 2
    q1_pane.locator(".btn-next-question").click()
    
    q2_pane = page.locator("#question-pane-2")
    expect(q2_pane).to_be_visible()
    expect(q2_pane.locator(".question-text")).to_contain_text("binary search")

    # Select Option C on Question 2 (Option C = "O(log n)")
    opt_c = q2_pane.locator('.option-item[data-opt="C"]')
    opt_c.click()
    expect(opt_c).to_have_class(re.compile(r"selected"))

    # Step 8: Click Previous to verify Answer Persistence
    q2_pane.locator(".btn-prev-question").click()
    expect(q1_pane).to_be_visible()
    # Option B on Question 1 must still be selected
    expect(q1_pane.locator('.option-item[data-opt="B"]')).to_have_class(re.compile(r"selected"))

    # Step 9: Jump to Question 3 via Palette
    page.locator("#palette-btn-3").click()
    q3_pane = page.locator("#question-pane-3")
    expect(q3_pane).to_be_visible()
    expect(q3_pane.locator(".question-text")).to_contain_text("train travels 120 km")

    # Select Option B on Question 3 (Option B = "60")
    q3_pane.locator('.option-item[data-opt="B"]').click()

    # Step 10: Open Submit Modal & Submit Assessment
    page.locator(".palette-card .btn-open-modal, #question-pane-3 .btn-open-modal").first.click()
    modal = page.locator("#submitConfirmModal")
    expect(modal).to_be_visible()

    # Confirm submission
    page.locator("#btnConfirmSubmit").click()

    # Step 11: Candidate Result View
    expect(page.locator(".result-hero, .result-header-card, h1").first).to_be_visible(timeout=10000)
    page_text = page.locator("body").inner_text()
    assert "Result" in page_text or "Score" in page_text or "Completed" in page_text

    # Step 12: Candidate Logs Out -> Employer Inspects Result
    page.locator(".nav-logout-btn").click()
    page.wait_for_url(f"{live_server.url}/")

    page.goto(f"{live_server.url}/employer/login/")
    expect(page.locator("h2, h1").first).to_contain_text(re.compile(r"Login|Sign In|Employer", re.I))
    page.fill('input[name="username"]', employer_user.username)
    page.fill('input[name="password"]', "TestPassword123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/employer/dashboard/")

    # Navigate to assessments list
    page.goto(f"{live_server.url}/employer/assessments/")
    expect(page.locator("body")).to_contain_text(assessment.title)
    expect(page.locator("body")).to_contain_text("Completed")


@pytest.mark.django_db(transaction=True)
def test_e2e_schedule_window_and_candidate_access_lifecycle(live_server, browser_context, test_setup_data):
    """Verify schedule window lifecycle:
    1. Employer creates assessment with AM/PM schedule and assigns candidates.
    2. Candidate opens before start -> blocked by 'Assessment Not Yet Open' gate.
    3. Scheduled time reached -> candidate can access instructions and start.
    4. Candidate remains able to start after scheduled start.
    5. Assessment closes at end time -> candidate is blocked with 'Assessment Closed'.
    """
    from datetime import timedelta
    from django.contrib.auth.models import User
    from django.utils import timezone
    from accounts.models import CandidateProfile
    from assessments.models import AssessmentGroup

    employer_user = test_setup_data["employer_user"]
    candidate_user = test_setup_data["candidate_user"]
    candidate_user_2 = User.objects.create_user(
        username="candidate2_e2e@test.com",
        email="candidate2_e2e@test.com",
        password="TestPassword123!",
        first_name="Priya",
        last_name="Sharma",
    )
    CandidateProfile.objects.create(user=candidate_user_2, profile_completed=True)

    page = browser_context.new_page()

    # Step 1: Employer Login & Bulk Create Assessment with AM/PM schedule
    page.goto(f"{live_server.url}/employer/login/")
    page.fill('input[name="username"]', employer_user.username)
    page.fill('input[name="password"]', "TestPassword123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/employer/dashboard/")

    # Navigate to Create Assessment page
    page.goto(f"{live_server.url}/employer/assessments/create/")
    expect(page.locator("h1")).to_contain_text("Create & Assign Assessment")

    # Set title and question count
    page.fill('input[name="title"]', "Schedule Window E2E Assessment")

    # Select both candidate checkboxes
    page.locator(f'input[name="candidates"][value="{candidate_user.id}"]').check()
    page.locator(f'input[name="candidates"][value="{candidate_user_2.id}"]').check()

    # Set schedule for future (Tomorrow 09:30 AM to 11:30 AM)
    tomorrow = timezone.localdate() + timedelta(days=1)
    tomorrow_str = tomorrow.isoformat()
    page.fill('input[name="start_date"]', tomorrow_str)
    page.fill('input[name="start_time"]', "09:30")
    page.fill('input[name="expire_date"]', tomorrow_str)
    page.fill('input[name="expire_time"]', "11:30")

    page.locator('input[name="logical_count"]').fill("1")
    page.locator('input[name="quant_count"]').fill("1")
    page.locator('input[name="technical_count"]').fill("1")

    # Submit form
    page.click("#btnSubmitAssessment")

    # Employer lands on Campaign detail dashboard
    page.wait_for_url(re.compile(r"/employer/campaign/\d+/"))
    expect(page.locator("h1")).to_contain_text("Schedule Window E2E Assessment")

    # Retrieve created assessments from DB
    group = AssessmentGroup.objects.filter(employer=employer_user, title="Schedule Window E2E Assessment").first()
    assert group is not None
    assert group.assessments.count() == 2

    assessment_cand1 = group.assessments.filter(candidate=candidate_user).first()
    assessment_cand2 = group.assessments.filter(candidate=candidate_user_2).first()
    assert assessment_cand1 is not None
    assert assessment_cand2 is not None

    # Step 2: Employer Logs Out -> Candidate 1 Logs In
    browser_context.clear_cookies()
    page.goto(f"{live_server.url}/candidate/login/")
    page.fill('input[name="username"]', candidate_user.username)
    page.fill('input[name="password"]', "TestPassword123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/candidate/dashboard/")

    # Candidate opens test URL BEFORE start time (scheduled for tomorrow)
    test_url_1 = f"{live_server.url}/test/{assessment_cand1.token}/"
    page.goto(test_url_1)

    # Verify candidate is blocked by "Assessment Not Yet Open"
    expect(page.locator("h1.gate-title")).to_have_text("Assessment Not Yet Open")
    expect(page.locator(".gate-desc")).to_contain_text("Scheduled to open:")
    expect(page.locator(".gate-desc")).to_contain_text("IST")
    expect(page.locator("#btnStartAssessment")).to_have_count(0)

    # Step 3: Scheduled time reached (simulate time opening)
    now = timezone.now()
    assessment_cand1.start_time = now - timedelta(minutes=5)
    assessment_cand1.expire_time = now + timedelta(hours=2)
    assessment_cand1.save(update_fields=["start_time", "expire_time"])

    # Reload page at scheduled time
    page.goto(test_url_1)

    # Instructions & system readiness page is now accessible
    expect(page.locator("h1")).to_contain_text(assessment_cand1.title)
    expect(page.locator(".system-check-card")).to_be_visible()

    # Step 4: Candidate remains able to start after scheduled start
    start_btn = page.locator("#btnStartAssessment")
    expect(start_btn).to_be_disabled()

    # Perform camera & mic verification
    page.locator("#btnTestMedia").click()
    expect(page.locator("#badgeCamera")).to_have_text("Ready", timeout=8000)
    expect(page.locator("#badgeMic")).to_have_text("Ready", timeout=8000)

    # Set fullscreen override and verify start button enables
    page.evaluate("() => { window.__fullscreenOverride = true; if (typeof updateCheckStatusUI === 'function') { updateCheckStatusUI(); } }")
    expect(start_btn).to_be_enabled(timeout=5000)

    # Candidate starts assessment
    start_btn.click()
    expect(page.locator(".test-header-bar")).to_be_visible(timeout=8000)
    expect(page.locator("#timerDisplay")).to_be_visible()
    expect(page.locator("#question-pane-1")).to_be_visible()

    # Step 5: Assessment closes at end time (simulate expiration for candidate 2 who hasn't started)
    assessment_cand2.start_time = now - timedelta(hours=3)
    assessment_cand2.expire_time = now - timedelta(minutes=1)
    assessment_cand2.save(update_fields=["start_time", "expire_time"])

    # Candidate 2 logs in
    browser_context.clear_cookies()
    page.goto(f"{live_server.url}/candidate/login/")
    page.fill('input[name="username"]', candidate_user_2.username)
    page.fill('input[name="password"]', "TestPassword123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/candidate/dashboard/")

    # Candidate 2 visits test URL past expiry
    test_url_2 = f"{live_server.url}/test/{assessment_cand2.token}/"
    page.goto(test_url_2)

    # Verify candidate 2 sees "Assessment Closed"
    expect(page.locator("h1.gate-title")).to_have_text("Assessment Closed")
    expect(page.locator(".gate-desc")).to_contain_text("Scheduled end:")
    expect(page.locator(".gate-desc")).to_contain_text("IST")

    assessment_cand2.refresh_from_db()
    assert assessment_cand2.status == Assessment.Status.EXPIRED
    assert assessment_cand2.candidate_status == Assessment.CandidateStatus.NOT_ATTENDED

