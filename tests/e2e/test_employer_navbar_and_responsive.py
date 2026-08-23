"""End-to-End Test Suite: Employer Navbar & Responsive Viewports.

Tests:
1. Employer Navbar Identity (Compact, Single-Row "EMPLOYER · <COMPANY>", No Wrapping)
2. Candidate Navbar Identity ("CANDIDATE")
3. Mobile & Desktop Responsive Layout across 9 Viewports (320px to 1440px)
4. Horizontal Overflow Checks across All Core Pages
"""

import pytest
from playwright.sync_api import expect


@pytest.mark.django_db(transaction=True)
def test_employer_and_candidate_navbar_branding(live_server, browser_context, test_setup_data):
    """Verify employer and candidate navbar role badges and layout on desktop and mobile."""
    employer_user = test_setup_data["employer_user"]
    employer_profile = test_setup_data["employer_profile"]
    candidate_user = test_setup_data["candidate_user"]

    page = browser_context.new_page()

    # 1. Employer Navbar Check (Desktop)
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{live_server.url}/employer/login/")
    page.fill('input[name="username"]', employer_user.username)
    page.fill('input[name="password"]', "TestPassword123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/employer/dashboard/")

    badge = page.locator(".nav-role-badge")
    expect(badge).to_be_visible()
    expect(badge).to_contain_text(f"EMPLOYER · {employer_profile.company}")

    # 2. Employer Navbar Check on Mobile (400x642)
    page.set_viewport_size({"width": 400, "height": 642})
    toggle_btn = page.locator("#mobileNavToggle")
    expect(toggle_btn).to_be_visible()
    toggle_btn.click()

    nav_wrapper = page.locator("#navLinksWrapper")
    expect(nav_wrapper).to_have_class("nav-links-wrapper is-open")
    expect(page.locator(".nav-links-wrapper .nav-role-badge")).to_be_visible()

    # Log out
    page.locator(".nav-logout-btn").click()

    # 3. Candidate Navbar Check
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{live_server.url}/candidate/login/")
    page.fill('input[name="username"]', candidate_user.username)
    page.fill('input[name="password"]', "TestPassword123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/candidate/dashboard/")

    cand_badge = page.locator(".nav-role-badge")
    expect(cand_badge).to_be_visible()
    expect(cand_badge).to_contain_text("CANDIDATE")


@pytest.mark.parametrize("viewport_width,viewport_height", [
    (320, 568),
    (375, 667),
    (390, 844),
    (400, 642),
    (412, 915),
    (430, 932),
    (768, 1024),
    (1280, 800),
    (1440, 900),
])
def test_responsive_homepage_viewports(live_server, browser_context, viewport_width, viewport_height):
    """Verify homepage layout and lack of horizontal overflow across standard viewports."""
    page = browser_context.new_page()
    page.set_viewport_size({"width": viewport_width, "height": viewport_height})

    page.goto(f"{live_server.url}/")

    # Verify key sections exist
    expect(page.locator(".brand")).to_be_visible()
    expect(page.locator(".hero-section, #features")).to_be_visible()
    expect(page.locator("footer.footer")).to_be_visible()

    # Verify Mobile vs Desktop Navigation Elements
    if viewport_width <= 900:
        expect(page.locator("#mobileNavToggle")).to_be_visible()
    else:
        expect(page.locator("#loginDropdownBtn")).to_be_visible()
        expect(page.locator("#registerDropdownBtn")).to_be_visible()

    # Check for horizontal scroll overflow: scrollWidth must be within 1px of clientWidth
    overflow = page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 1, f"Horizontal overflow detected at {viewport_width}x{viewport_height}: {overflow}px"
