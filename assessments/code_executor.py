"""Safe code execution abstraction for Coding Assessment.

ARCHITECTURE & SECURITY POLICY:
- Arbitrary code execution is NOT executed via eval(), exec(), os.system(), or uncontained subprocesses.
- In this phase, a secure service interface (BaseCodeExecutionService) and a safe
  Mock/Development execution service (MockCodeExecutionService) are provided.
- In Phase 2, a sandboxed microservice (e.g. Judge0, Piston API, or isolated Docker worker)
  can be plugged in seamlessly by setting the active execution service.
"""

import ast
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TestCaseExecutionResult:
    """Result of running a single test case."""
    test_case_id: Optional[int]
    order: int
    is_sample: bool
    status: str  # "PASSED", "FAILED", "SYNTAX_ERROR", "RUNTIME_ERROR", "TIMEOUT"
    input_data: str
    expected_output: str
    actual_output: str
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float = 0.0
    passed: bool = False

    def to_dict(self, hide_details: bool = False) -> Dict[str, Any]:
        """Format test case result for JSON API response.
        
        If hide_details is True (for hidden test cases), input and expected/actual outputs
        are omitted to prevent test case leaking to the candidate.
        """
        if hide_details and not self.is_sample:
            return {
                "test_case_id": self.test_case_id,
                "order": self.order,
                "is_sample": False,
                "status": self.status,
                "passed": self.passed,
                "execution_time_ms": self.execution_time_ms,
                "stdout": "",
                "stderr": self.stderr if self.status == "SYNTAX_ERROR" else "",
            }
        return {
            "test_case_id": self.test_case_id,
            "order": self.order,
            "is_sample": self.is_sample,
            "status": self.status,
            "passed": self.passed,
            "input_data": self.input_data,
            "expected_output": self.expected_output,
            "actual_output": self.actual_output,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class CodeRunSummary:
    """Aggregated summary of running code across a set of test cases."""
    language: str
    total_test_cases: int
    passed_test_cases: int
    score_percentage: float
    results: List[TestCaseExecutionResult] = field(default_factory=list)
    has_syntax_error: bool = False
    syntax_error_message: str = ""

    def to_dict(self, hide_hidden_details: bool = True) -> Dict[str, Any]:
        return {
            "language": self.language,
            "total_test_cases": self.total_test_cases,
            "passed_test_cases": self.passed_test_cases,
            "score_percentage": self.score_percentage,
            "has_syntax_error": self.has_syntax_error,
            "syntax_error_message": self.syntax_error_message,
            "results": [r.to_dict(hide_details=hide_hidden_details) for r in self.results],
        }


class BaseCodeExecutionService(ABC):
    """Abstract base class for code execution services."""

    @abstractmethod
    def validate_syntax(self, language: str, source_code: str) -> tuple[bool, str]:
        """Validate basic source code syntax without executing untrusted code."""
        pass

    @abstractmethod
    def execute_test_cases(
        self,
        language: str,
        source_code: str,
        test_cases: List[Any],
        only_samples: bool = False,
    ) -> CodeRunSummary:
        """Run candidate source code against test cases."""
        pass


class MockCodeExecutionService(BaseCodeExecutionService):
    """Safe Development & Mock Execution Engine.
    
    Validates code syntax safely and simulates test case outputs for development,
    unit testing, and demonstrations without executing arbitrary code inside the host process.
    """

    def validate_syntax(self, language: str, source_code: str) -> tuple[bool, str]:
        code = source_code.strip()
        if not code:
            return False, "Source code cannot be empty."

        lang = language.lower().strip()
        if lang in ("python", "py", "python3"):
            try:
                ast.parse(code)
                return True, ""
            except SyntaxError as e:
                return False, f"Python Syntax Error (line {e.lineno}): {e.msg}"
        elif lang in ("javascript", "js"):
            # Basic structural bracket balance check
            brackets = {"(": ")", "{": "}", "[": "]"}
            stack = []
            for ch in code:
                if ch in brackets:
                    stack.append(brackets[ch])
                elif ch in brackets.values():
                    if not stack or stack.pop() != ch:
                        return False, "JavaScript Syntax Error: Unbalanced brackets or braces."
            return True, ""
        elif lang in ("java", "cpp", "c++"):
            # Basic validation that main function / class structure exists
            if lang == "java" and "class " not in code and "public " not in code:
                return False, "Java Syntax Error: Class or method structure not found."
            return True, ""
        return True, ""

    def execute_test_cases(
        self,
        language: str,
        source_code: str,
        test_cases: List[Any],
        only_samples: bool = False,
    ) -> CodeRunSummary:
        t0 = time.time()
        is_valid_syntax, syntax_msg = self.validate_syntax(language, source_code)

        target_test_cases = [tc for tc in test_cases if not only_samples or tc.is_sample]
        total = len(target_test_cases)

        if not is_valid_syntax:
            results = []
            for tc in target_test_cases:
                results.append(
                    TestCaseExecutionResult(
                        test_case_id=getattr(tc, "id", None),
                        order=getattr(tc, "order", 1),
                        is_sample=getattr(tc, "is_sample", False),
                        status="SYNTAX_ERROR",
                        input_data=tc.input_data,
                        expected_output=tc.expected_output,
                        actual_output="",
                        stderr=syntax_msg,
                        passed=False,
                    )
                )
            return CodeRunSummary(
                language=language,
                total_test_cases=total,
                passed_test_cases=0,
                score_percentage=0.0,
                results=results,
                has_syntax_error=True,
                syntax_error_message=syntax_msg,
            )

        # Code passed syntax validation -> evaluate test cases
        # In this safe mock/development evaluator, if the candidate's code contains logic
        # (e.g. function body, return statements, or solution logic), we check if the code
        # has standard solution keywords or implementation to determine pass/fail realistically.
        results = []
        passed_count = 0

        clean_code = source_code.strip()
        has_substantive_code = len(clean_code) >= 10 and (
            "return" in clean_code
            or "print" in clean_code
            or "System.out" in clean_code
            or "console.log" in clean_code
            or "cout" in clean_code
        )


        for tc in target_test_cases:
            exp_out = tc.expected_output.strip()
            # If code is substantive, treat sample and standard cases as passed
            is_pass = has_substantive_code
            actual_out = exp_out if is_pass else "(no output or default return)"
            status = "PASSED" if is_pass else "FAILED"
            if is_pass:
                passed_count += 1

            results.append(
                TestCaseExecutionResult(
                    test_case_id=getattr(tc, "id", None),
                    order=getattr(tc, "order", 1),
                    is_sample=getattr(tc, "is_sample", False),
                    status=status,
                    input_data=tc.input_data,
                    expected_output=exp_out,
                    actual_output=actual_out,
                    stdout=f"Test case #{getattr(tc, 'order', 1)} execution finished in 12ms",
                    execution_time_ms=12.5,
                    passed=is_pass,
                )
            )

        pct = round((passed_count / total * 100.0), 2) if total > 0 else 0.0
        return CodeRunSummary(
            language=language,
            total_test_cases=total,
            passed_test_cases=passed_count,
            score_percentage=pct,
            results=results,
            has_syntax_error=False,
        )


# =========================================================================
# Phase 2 Extension Point:
# Configure external sandbox (e.g. Judge0 API, Docker isolate, or Piston)
# =========================================================================
_default_executor: BaseCodeExecutionService = MockCodeExecutionService()


def get_code_executor() -> BaseCodeExecutionService:
    """Return the active code execution service instance."""
    return _default_executor


def set_code_executor(executor: BaseCodeExecutionService) -> None:
    """Configure a custom code executor (e.g. Sandboxed Judge0 client in Phase 2)."""
    global _default_executor
    _default_executor = executor