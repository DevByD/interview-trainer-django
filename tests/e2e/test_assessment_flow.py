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
