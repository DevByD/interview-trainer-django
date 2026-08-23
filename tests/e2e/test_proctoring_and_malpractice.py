"""End-to-End Test Suite: Proctoring & Malpractice Handling.

Tests:
1. Media Permission Denied: System check properly rejects entry when camera/mic denied.
2. Tab-Switch / Page Visibility: Accurate capture of tab switching events.
3. 3-Warning Malpractice Policy: Warning 1 -> Warning 2 -> Warning 3 -> Auto-Submission.
4. Server-Authoritative Database State on Malpractice Auto-Submission.
"""

import pytest
import re
from playwright.sync_api import expect
from assessments.models import Assessment, Answer
from results.models import Result


@pytest.mark.django_db(transaction=True)
def test_camera_and_mic_denied_prevents_start(live_server, browser_context, test_setup_data):
    """Verify that when media permissions are denied, system check fails and test cannot be started."""
    candidate_user = test_setup_data["candidate_user"]
    assessment = test_setup_data["assessment"]

    page = browser_context.new_page()

    # Override getUserMedia in page to simulate candidate denying permission
    page.add_init_script("""
        navigator.mediaDevices.getUserMedia = (constraints) => {
            return Promise.reject(new DOMException('Camera and microphone permission denied by candidate.', 'NotAllowedError'));
        };
    """)

    # Log in candidate
    page.goto(f"{live_server.url}/candidate/login/")
    page.fill('input[name="username"]', candidate_user.username)
    page.fill('input[name="password"]', "TestPassword123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/candidate/dashboard/")

    # Open test instructions
    page.goto(f"{live_server.url}/test/{assessment.token}/")

    # Start button must remain strictly disabled
    start_btn = page.locator("#btnStartAssessment")
    expect(start_btn).to_be_disabled()

    # Trigger media check
    page.locator("#btnTestMedia").click()

    # Error alert must appear
    error_alert = page.locator("#checkErrorAlert")
    expect(error_alert).to_be_visible(timeout=8000)
    expect(page.locator("#checkErrorMessage")).to_contain_text(re.compile(r"required|denied|access|failed", re.I))

    # Camera and/or Mic badges must indicate failure / required
    expect(page.locator("#badgeCamera")).to_have_text("Required")
    expect(page.locator("#badgeMic")).to_have_text("Required")

    # Start button MUST remain disabled
    expect(start_btn).to_be_disabled()


@pytest.mark.django_db(transaction=True)
def test_tab_switch_three_warnings_auto_submit(live_server, browser_context, test_setup_data):
    """Verify tab switch detection, 3-warning progression, and automatic submission."""
    candidate_user = test_setup_data["candidate_user"]
    assessment = test_setup_data["assessment"]

    page = browser_context.new_page()

    # Log in candidate
    page.goto(f"{live_server.url}/candidate/login/")
    page.fill('input[name="username"]', candidate_user.username)
    page.fill('input[name="password"]', "TestPassword123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/candidate/dashboard/")

    # Open test instructions & pass system check
    page.goto(f"{live_server.url}/test/{assessment.token}/")
    page.locator("#btnTestMedia").click()
    expect(page.locator("#badgeCamera")).to_have_text("Ready", timeout=8000)
    page.evaluate("() => { window.__fullscreenOverride = true; if (typeof updateCheckStatusUI === 'function') { updateCheckStatusUI(); } }")

    start_btn = page.locator("#btnStartAssessment")
    expect(start_btn).to_be_enabled(timeout=5000)
    start_btn.click()

    # Assessment is now ONGOING
    expect(page.locator(".test-header-bar")).to_be_visible(timeout=8000)
    page.evaluate("() => { window.__fullscreenOverride = true; }")
    proctoring_modal = page.locator("#proctoringModal")

    # VIOLATION 1: Trigger first tab switch
    page.evaluate("""async () => {
        if (typeof reportViolation === 'function') {
            await reportViolation('TAB_SWITCH');
        }
    }""")

    expect(page.locator("#headerWarningCount")).to_have_text("1", timeout=8000)
    expect(page.locator("#proctoringCountNum")).to_have_text("1")
    expect(proctoring_modal).to_be_visible()

    # Dismiss/return to test
    page.locator("#btnProctoringReenterFullscreen").click()
    expect(proctoring_modal).not_to_be_visible()

    # Wait for server debounce (2.6s)
    page.wait_for_timeout(2600)

    # VIOLATION 2: Trigger second tab switch
    page.evaluate("""async () => {
        if (typeof reportViolation === 'function') {
            await reportViolation('TAB_SWITCH');
        }
    }""")

    expect(page.locator("#headerWarningCount")).to_have_text("2", timeout=8000)
    expect(page.locator("#proctoringCountNum")).to_have_text("2")
    expect(proctoring_modal).to_be_visible()

    # Dismiss/return to test
    page.locator("#btnProctoringReenterFullscreen").click()
    expect(proctoring_modal).not_to_be_visible()

    # Wait for server debounce (2.6s)
    page.wait_for_timeout(2600)

    # VIOLATION 3: Trigger third tab switch -> Triggers termination & auto-submission
    page.evaluate("""async () => {
        if (typeof reportViolation === 'function') {
            await reportViolation('TAB_SWITCH');
        }
    }""")

    expect(page.locator("#proctoringModalTitle")).to_have_text("Assessment Terminated", timeout=8000)
    expect(page.locator("#proctoringCountNum")).to_have_text("3")

    # Wait for auto-redirect or submission
    page.wait_for_timeout(3500)

    # Verify Database Consistency
    assessment.refresh_from_db()
    assert assessment.status == Assessment.Status.COMPLETED
    assert assessment.candidate_status == Assessment.CandidateStatus.ATTENDED
    assert assessment.violation_count == 3
    assert assessment.malpractice_status is True
    assert assessment.auto_submitted_for_malpractice is True
    assert "malpractice" in assessment.submission_reason.lower() or "violation" in assessment.submission_reason.lower()

    # Verify Result record
    result = Result.objects.get(assessment=assessment)
    assert result.auto_submitted_for_malpractice is True
    assert result.violation_count == 3
