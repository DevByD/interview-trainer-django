"""Playwright End-to-End tests for the Admin Management Suite and Question Bank CRUD."""

import pytest
from django.contrib.auth.models import User
from playwright.sync_api import Page, expect

from assessments.models import Question, CodingQuestion


@pytest.mark.django_db
def test_admin_portal_full_flow(live_server, browser_context, test_setup_data):
    """Complete end-to-end user journey for Admin Portal oversight, Question Bank CRUD, and telemetry."""
    # 1. Create superadmin user
    admin_user = User.objects.create_superuser(
        username="admin_e2e@platform.com",
        email="admin_e2e@platform.com",
        password="AdminSecurePassword123!",
    )

    page: Page = browser_context.new_page()

    # 2. Login as Admin via Employer/Admin Login form
    page.goto(f"{live_server.url}/employer/login/")
    page.fill('input[name="username"]', "admin_e2e@platform.com")
    page.fill('input[name="password"]', "AdminSecurePassword123!")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    # 3. Navigate to Admin Portal Dashboard
    page.goto(f"{live_server.url}/admin-portal/")
    expect(page.locator("h1")).to_contain_text("System Overview & Telemetry")
    expect(page.locator(".metric-card")).to_have_count(5)

    # 4. Navigate to Question Bank
    page.click('a:has-text("Question Bank")')
    page.wait_for_load_state("networkidle")
    expect(page.locator("h1")).to_contain_text("Question Bank Management")
    expect(page.locator("#bulkActionForm")).to_be_visible()

    # 5. Create new MCQ Question
    page.click('a:has-text("+ New MCQ")')
    page.wait_for_load_state("networkidle")
    expect(page.locator("h1")).to_contain_text("Create MCQ Question")

    page.select_option('select[name="section"]', "LOGICAL")
    page.fill('input[name="category"]', "Blood Relations")
    page.select_option('select[name="difficulty"]', "EASY")
    page.fill('textarea[name="question_text"]', "Pointing to a photograph, A said 'She is the mother of my brother'. How is she related to A?")
    page.fill('input[name="option_a"]', "Mother")
    page.fill('input[name="option_b"]', "Sister")
    page.fill('input[name="option_c"]', "Aunt")
    page.fill('input[name="option_d"]', "Daughter")
    page.select_option('select[name="correct_answer"]', "A")
    page.fill('textarea[name="explanation"]', "The mother of one's brother is one's mother.")
    page.click('button:has-text("Save MCQ Question")')
    page.wait_for_load_state("networkidle")

    # Verify MCQ appeared in Question Bank
    expect(page.locator("body")).to_contain_text("Pointing to a photograph")

    # 6. Filter Questions by Section
    page.select_option('select[name="section"]', "LOGICAL")
    page.click('button:has-text("Filter")')
    page.wait_for_load_state("networkidle")
    expect(page.locator("body")).to_contain_text("Pointing to a photograph")

    # 7. Navigate to Assessments
    page.click('a:has-text("Assessments")')
    page.wait_for_load_state("networkidle")
    expect(page.locator("h1")).to_contain_text("Platform Assessments Management")
    expect(page.locator("body")).to_contain_text("Software Engineering Assessment")

    # 8. Inspect Assessment Detail
    page.click('a:has-text("Inspect →")')
    page.wait_for_load_state("networkidle")
    expect(page.locator("h1")).to_contain_text("Assessment Inspection")
    expect(page.locator("body")).to_contain_text("Acme Corp")
    expect(page.locator("body")).to_contain_text("Aptitude Questions & Candidate Responses")

    # 9. Navigate to Analytics
    page.goto(f"{live_server.url}/admin-portal/analytics/")
    expect(page.locator("h1")).to_contain_text("Results & Evaluation Analytics")

    # 10. Navigate to Proctoring Audit
    page.goto(f"{live_server.url}/admin-portal/proctoring/")
    expect(page.locator("h1")).to_contain_text("Proctoring & Malpractice Telemetry")

    # 11. Navigate to AI Governance
    page.goto(f"{live_server.url}/admin-portal/ai/")
    expect(page.locator("h1")).to_contain_text("AI Governance & Synthesis Audit")
    expect(page.locator("body")).to_contain_text("AI Decision Support & Governance Policy")

    # 12. Navigate to Reports
    page.goto(f"{live_server.url}/admin-portal/reports/")
    expect(page.locator("h1")).to_contain_text("Platform Reports & Data Exports")
    expect(page.locator('a:has-text("Download Candidate CSV")')).to_be_visible()

    # 13. Navigate to Activity Logs
    page.goto(f"{live_server.url}/admin-portal/activity-logs/")
    expect(page.locator("h1")).to_contain_text("Admin Activity Audit Log")
    expect(page.locator("body")).to_contain_text("Created MCQ Question")

    # 14. Responsive Layout Test (375px Mobile Viewport)
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(f"{live_server.url}/admin-portal/")
    expect(page.locator("#mobileNavToggle")).to_be_visible()
    # Click mobile hamburger
    page.click("#mobileNavToggle")
    expect(page.locator("#navLinksWrapper")).to_have_class("nav-links-wrapper is-open")
