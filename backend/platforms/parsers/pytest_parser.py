"""
pytest_parser.py — Parse raw pytest / flake8 / mypy output into structured errors.
"""

from __future__ import annotations
import re


# ── pytest ─────────────────────────────────────────────────────────────────

# FAILED tests/test_auth.py::TestLogin::test_invalid_password - AssertionError
_PYTEST_FAIL = re.compile(
    r"^FAILED\s+(?P<file>[^::\s]+)::(?P<test>[^\s]+)\s*(?:-\s*(?P<msg>.+))?$",
    re.MULTILINE,
)
# ERROR tests/test_auth.py::TestLogin::test_something - SomeError
_PYTEST_ERROR = re.compile(
    r"^ERROR\s+(?P<file>[^::\s]+)::(?P<test>[^\s]+)\s*(?:-\s*(?P<msg>.+))?$",
    re.MULTILINE,
)
# ===  5 passed, 2 failed in 1.23s ===
_PYTEST_SUMMARY = re.compile(
    r"=+\s+(?:(?P<passed>\d+) passed)?(?:,?\s*(?P<failed>\d+) failed)?(?:,?\s*(?P<error>\d+) error)?\s+in\s+[\d.]+s"
)
# Short: 5/7 style extracted from summary
_PYTEST_SHORT   = re.compile(r"(\d+) passed")


def parse_pytest(output: str) -> dict:
    errors = []

    for m in _PYTEST_FAIL.finditer(output):
        errors.append(_make(
            "test_failure",
            m.group("file"), 0, 0,
            f"FAILED {m.group('test')}: {m.group('msg') or ''}".strip(),
        ))

    for m in _PYTEST_ERROR.finditer(output):
        errors.append(_make(
            "test_error",
            m.group("file"), 0, 0,
            f"ERROR {m.group('test')}: {m.group('msg') or ''}".strip(),
        ))

    summary_m = _PYTEST_SUMMARY.search(output)
    test_summary = ""
    if summary_m:
        passed  = int(summary_m.group("passed") or 0)
        failed  = int(summary_m.group("failed") or 0)
        errored = int(summary_m.group("error")  or 0)
        total   = passed + failed + errored
        test_summary = f"{passed}/{total} passed"

    passed_only = "passed" in output and "failed" not in output and "error" not in output

    return {
        "tests": "ok" if passed_only else ("fail" if errors else "unknown"),
        "test_summary": test_summary,
        "errors": errors,
    }


# ── flake8 ────────────────────────────────────────────────────────────────

# path/to/file.py:10:5: E302 expected 2 blank lines, found 1
_FLAKE8_LINE = re.compile(
    r"^(?P<file>[^:\s][^:]*\.py):(?P<line>\d+):(?P<col>\d+):\s*(?P<code>[A-Z]\d+)\s+(?P<msg>.+)$",
    re.MULTILINE,
)


def parse_flake8(output: str) -> dict:
    errors = []
    for m in _FLAKE8_LINE.finditer(output):
        code = m.group("code")
        sev  = "lint_error" if code.startswith("E") else "lint_warning"
        errors.append(_make(
            sev, m.group("file").strip(),
            int(m.group("line")), int(m.group("col")),
            f"{code} {m.group('msg').strip()}",
        ))
    return {
        "lint": "ok" if not errors else "fail",
        "errors": errors,
    }


# ── mypy ──────────────────────────────────────────────────────────────────

# path/to/file.py:10: error: Argument 1 to "foo" ...
_MYPY_LINE = re.compile(
    r"^(?P<file>[^:\s][^:]*\.py):(?P<line>\d+):\s*(?P<sev>error|warning|note):\s*(?P<msg>.+)$",
    re.MULTILINE,
)
_MYPY_SUCCESS = re.compile(r"^Success: no issues found", re.MULTILINE)


def parse_mypy(output: str) -> dict:
    errors, warnings = [], []
    for m in _MYPY_LINE.finditer(output):
        sev = m.group("sev")
        entry = _make(
            "lint_error" if sev == "error" else "lint_warning",
            m.group("file").strip(), int(m.group("line")), 0,
            m.group("msg").strip(),
        )
        (errors if sev == "error" else warnings).append(entry)
    return {
        "mypy": "ok" if (_MYPY_SUCCESS.search(output) or not errors) else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def parse_django_full(build_out: str, lint_out: str, test_out: str) -> dict:
    """
    Merge Django check + flake8/mypy + pytest results into one structured report.
    lint_out is expected to be flake8 + mypy concatenated.
    """
    # Django manage.py check: look for SystemCheckError
    build_ok = "System check identified no issues" in build_out
    build_err = "SystemCheckError" in build_out or "ERRORS:" in build_out

    flake = parse_flake8(lint_out)
    mypy  = parse_mypy(lint_out)
    tests = parse_pytest(test_out)

    all_errors = flake["errors"] + mypy["errors"] + tests["errors"]

    # Django check errors
    if build_err:
        for line in build_out.splitlines():
            if line.strip().startswith("ERRORS:") or ": E" in line:
                all_errors.append(_make("build_error", "manage.py", 0, 0, line.strip()))

    return {
        "build":    "ok" if build_ok else ("fail" if build_err else "unknown"),
        "lint":     "ok" if (flake["lint"] == "ok" and mypy["mypy"] == "ok") else "fail",
        "tests":    tests["test_summary"] or tests["tests"],
        "errors":   all_errors,
        "warnings": mypy["warnings"],
        "status":   "pass" if not all_errors else "fail",
    }


def _make(type_: str, file: str, line: int, col: int, msg: str) -> dict:
    return {
        "type": type_, "file": file, "line": line,
        "column": col, "message": msg, "acceptance_criterion": "unknown",
    }
