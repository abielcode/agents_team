"""
gradle_parser.py — Parse raw Gradle / ktlint / JUnit output into structured errors.
"""

from __future__ import annotations
import re


# ── Gradle build errors ────────────────────────────────────────────────────

# e: /path/to/File.kt: (23, 5): error: unresolved reference: foo
_KOTLIN_ERROR = re.compile(
    r"^(?P<sev>e|w):\s*(?P<file>[^:]+\.kt):\s*\((?P<line>\d+),\s*(?P<col>\d+)\):\s*(?P<msg>.+)$",
    re.MULTILINE,
)

# FAILURE: Build failed with an exception.
_BUILD_FAILED    = re.compile(r"BUILD FAILED")
_BUILD_SUCCEEDED = re.compile(r"BUILD SUCCESSFUL")

# Gradle test results
# Tests run: 10, Failures: 2, Errors: 0, Skipped: 0
_TEST_SUMMARY = re.compile(r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)")
# JUnit5 style: FailedTest > testMethod() FAILED
_TEST_FAIL_LINE  = re.compile(r"^\s*> Task :test\b.*FAILED", re.MULTILINE)
_TEST_METHOD     = re.compile(r"^\s+\w[\w.]+\s*>\s*(.+?)\(\)\s+FAILED", re.MULTILINE)


def parse_gradle(output: str) -> dict:
    errors, warnings = [], []
    for m in _KOTLIN_ERROR.finditer(output):
        sev = m.group("sev")
        entry = _make(
            "build_error" if sev == "e" else "lint_warning",
            m.group("file").strip(), int(m.group("line")),
            int(m.group("col")), m.group("msg").strip(),
        )
        (errors if sev == "e" else warnings).append(entry)

    return {
        "build": "fail" if _BUILD_FAILED.search(output) else (
                 "ok" if _BUILD_SUCCEEDED.search(output) else "unknown"),
        "errors": errors,
        "warnings": warnings,
    }


# ── ktlint ────────────────────────────────────────────────────────────────

# /path/to/File.kt:10:1: error: ... (ktlint)
_KTLINT_LINE = re.compile(
    r"^(?P<file>[^:\s][^:]*\.kt):(?P<line>\d+):(?P<col>\d+):\s*(?P<msg>.+)$",
    re.MULTILINE,
)


def parse_ktlint(output: str) -> dict:
    errors = []
    for m in _KTLINT_LINE.finditer(output):
        errors.append(_make(
            "lint_error",
            m.group("file").strip(), int(m.group("line")),
            int(m.group("col")), m.group("msg").strip(),
        ))
    return {
        "lint": "ok" if not errors else "fail",
        "errors": errors,
    }


# ── JUnit5 / Gradle test results ──────────────────────────────────────────

def parse_gradle_tests(output: str) -> dict:
    summary_m = _TEST_SUMMARY.search(output)
    test_summary = ""
    if summary_m:
        total    = int(summary_m.group(1))
        failures = int(summary_m.group(2))
        errors_n = int(summary_m.group(3))
        passed   = total - failures - errors_n
        test_summary = f"{passed}/{total} passed"

    failed_tests = []
    for m in _TEST_METHOD.finditer(output):
        failed_tests.append(_make(
            "test_failure", "", 0, 0,
            f"Test failed: {m.group(1).strip()}",
        ))

    return {
        "tests": "ok" if not _TEST_FAIL_LINE.search(output) else "fail",
        "test_summary": test_summary,
        "errors": failed_tests,
    }


def parse_android_full(build_out: str, lint_out: str, test_out: str) -> dict:
    """Merge Gradle + ktlint + JUnit results into one structured report."""
    build  = parse_gradle(build_out)
    lint   = parse_ktlint(lint_out)
    tests  = parse_gradle_tests(test_out)
    all_errors = build["errors"] + lint["errors"] + tests["errors"]
    return {
        "build":    build["build"],
        "lint":     lint["lint"],
        "tests":    tests["test_summary"] or tests["tests"],
        "errors":   all_errors,
        "warnings": build["warnings"],
        "status":   "pass" if not all_errors else "fail",
    }


def _make(type_: str, file: str, line: int, col: int, msg: str) -> dict:
    return {
        "type": type_, "file": file, "line": line,
        "column": col, "message": msg, "acceptance_criterion": "unknown",
    }
