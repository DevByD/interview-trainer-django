"""End-to-End Test Suite: Coding Assessment Workflow.

Tests:
1. Candidate Coding Problem Rendering (DSA title, category, difficulty, constraints)
2. Editor Clean Startup: Starts empty except for safe minimal comment scaffold
3. Multi-Language Selector (Python, Java, C++, JavaScript)
4. Run Code: Executes candidate code against sample test cases
5. Submit Code: Evaluates candidate code against hidden/public test cases and updates problem score
"""

import pytest
from playwright.sync_api import expect
from assessments.models import Assessment, CodingSubmission


@pytest.mark.django_db(transaction=True)
def test_coding_assessment_execution_and_scoring(live_server, browser_context, test_setup_data):
    """Verify coding assessment interface, language switching, execution, and submission."""
    candidate_user = test_setup_data["candidate_user"]
    assessment = test_setup_data["assessment"]
    cq = test_setup_data["cq"]

    # Mark assessment ongoing for direct coding entry
    assessment.status = Assessment.Status.ONGOING
    assessment.save()

    page = browser_context.new_page()

    # Log in candidate
    page.goto(f"{live_server.url}/candidate/login/")
    page.fill('input[name="username"]', candidate_user.username)
    page.fill('input[name="password"]', "TestPassword123!")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{live_server.url}/candidate/dashboard/")

    # Open Coding assessment page
    coding_url = f"{live_server.url}/test/{assessment.token}/coding/"
    page.goto(coding_url)

    # 1. Verify Problem Elements
    expect(page.locator("#problemTitle")).to_contain_text(cq.title)
    expect(page.locator("#problemDifficulty")).to_be_visible()
    expect(page.locator("#problemDescription")).to_contain_text("Given an array of integers")
    expect(page.locator("#problemSampleInput")).to_contain_text("2 7 11 15")

    # 2. Verify Editor Starts Empty / Safe Scaffold Only (No solution preloaded)
    editor_code = page.evaluate("""() => {
        if (window.monacoEditor) {
            return window.monacoEditor.getValue();
        }
        const ta = document.getElementById('codeEditorTextarea');
        return ta ? ta.value : '';
    }""")
    assert "return" not in editor_code or "def twoSum" not in editor_code

    # 3. Test Language Selector Switching
    lang_select = page.locator("#languageSelect")
    expect(lang_select).to_be_visible()
    lang_select.select_option("python")
    expect(lang_select).to_have_value("python")

    # 4. Write Python Solution into Editor
    python_solution = (
        "import sys\n"
        "lines = sys.stdin.read().strip().split('\\n')\n"
        "if len(lines) >= 2:\n"
        "    nums = list(map(int, lines[0].split()))\n"
        "    target = int(lines[1].strip())\n"
        "    lookup = {}\n"
        "    for i, n in enumerate(nums):\n"
        "        comp = target - n\n"
        "        if comp in lookup:\n"
        "            print(f'{lookup[comp]} {i}')\n"
        "            break\n"
        "        lookup[n] = i\n"
    )

    page.evaluate("""(code) => {
        if (window.monacoEditor) {
            window.monacoEditor.setValue(code);
        } else {
            const ta = document.getElementById('codeEditorTextarea');
            if (ta) {
                ta.value = code;
                ta.dispatchEvent(new Event('input'));
            }
        }
    }""", python_solution)

    # 5. Run Code (Sample test cases)
    run_btn = page.locator("#btnRunCode")
    run_btn.click()

    # Wait for execution results in console
    expect(page.locator("#summaryBadge")).to_contain_text("Passed", timeout=12000)

    # 6. Submit Code (All test cases)
    submit_btn = page.locator("#btnSubmitProblem")
    submit_btn.click()

    # Verify Submission banner / summary
    expect(page.locator("#summaryBadge")).to_contain_text("Passed: 3 / 3", timeout=15000)
    expect(page.locator("#submissionAlertBanner")).to_be_visible()

    # Verify Database Submission Record
    submission = CodingSubmission.objects.get(assessment=assessment, question=cq)
    assert submission.passed_test_cases == 3
    assert submission.total_test_cases == 3
    assert submission.score == 100.0 or submission.is_submitted is True
