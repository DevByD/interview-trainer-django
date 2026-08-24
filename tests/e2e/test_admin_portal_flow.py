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

    # 1. Admin Login footer link exists on landing page and clicks to /admin-portal/login/
    page.goto(f"{live_server.url}/")
    footer_admin_link = page.locator('footer a:has-text("Admin Login")').first
    expect(footer_admin_link).to_be_visible()
    footer_admin_link.click()
    page.wait_for_load_state("networkidle")
    expect(page).to_have_url(f"{live_server.url}/admin-portal/login/")
    expect(page.locator("h1")).to_contain_text("Admin Portal")
    expect(page.locator("body")).to_contain_text("Authorized administrators only.")

    # 2. Admin can login via Admin Login portal
    page.fill('input[name="username"]', "admin_e2e@platform.com")
    page.fill('input[name="password"]', "AdminSecurePassword123!")
    page.click('button:has-text("Admin Login")')
    page.wait_for_load_state("networkidle")

    # 4. Admin can access Admin Portal
    expect(page).to_have_url(f"{live_server.url}/admin-portal/")
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

    # 14. Admin Logout & Post-Logout Access Revocation
    page.click('button:has-text("Logout")')
    page.wait_for_load_state("networkidle")
    # Verify redirected to home/login and cannot access portal
    page.goto(f"{live_server.url}/admin-portal/")
    expect(page).to_have_url(f"{live_server.url}/admin-portal/login/?next=/admin-portal/")

    # 15. Responsive Layout Testing (320px to 1440px)
    viewports = [
        {"width": 320, "height": 568},
        {"width": 375, "height": 667},
        {"width": 390, "height": 844},
        {"width": 400, "height": 800},
        {"width": 412, "height": 915},
        {"width": 430, "height": 932},
        {"width": 768, "height": 1024},
        {"width": 1024, "height": 768},
        {"width": 1440, "height": 900},
    ]

    for vp in viewports:
        page.set_viewport_size(vp)
        # Test Public Footer
        page.goto(f"{live_server.url}/")
        expect(page.locator('footer a:has-text("Admin Login")').first).to_be_visible()

        # Test Admin Login Page
        page.goto(f"{live_server.url}/admin-portal/login/")
        expect(page.locator("h1")).to_contain_text("Admin Portal")
        expect(page.locator('button:has-text("Admin Login")')).to_be_visible()

        # Verify no horizontal scrollbar
        has_h_scroll = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        assert not has_h_scroll, f"Horizontal scroll detected at viewport {vp['width']}x{vp['height']}"
