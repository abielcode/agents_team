"""
xcodebuild_parser.py — Parse raw xcodebuild / swiftlint output into structured errors.
"""

from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass
class BuildError:
    type: str       # build_error | lint_error | lint_warning | test_failure
    file: str
    line: int
    column: int
    message: str


# ── Regex patterns ─────────────────────────────────────────────────────────

# /path/to/File.swift:23:5: error: use of unresolved identifier 'foo'
_XCODE_DIAG = re.compile(
    r"^(?P<file>[^\s:][^:]*\.swift):(?P<line>\d+):(?P<col>\d+):\s*"
    r"(?P<sev>error|warning|note):\s*(?P<msg>.+)$",
    re.MULTILINE,
)
_BUILD_SUCCEEDED = re.compile(r"\*\*\s*BUILD SUCCEEDED\s*\*\*")
_BUILD_FAILED    = re.compile(r"\*\*\s*BUILD FAILED\s*\*\*")
_TEST_SUCCEEDED  = re.compile(r"\*\*\s*TEST SUCCEEDED\s*\*\*")
_TEST_FAILED_HDR = re.compile(r"\*\*\s*TEST FAILED\s*\*\*")
_TEST_COUNT      = re.compile(r"Executed (\d+) tests?, with (\d+) failures?")

# swiftlint: same format as xcodebuild diagnostics
_SWIFTLINT_DIAG  = _XCODE_DIAG


def parse_xcodebuild(output: str) -> dict:
    errors, warnings = [], []
    for m in _XCODE_DIAG.finditer(output):
        sev = m.group("sev")
        entry = _make(
            "build_error" if sev == "error" else "lint_warning",
            m.group("file").strip(), int(m.group("line")),
            int(m.group("col")), m.group("msg").strip(),
        )
        (errors if sev == "error" else warnings).append(entry)

    count_m = _TEST_COUNT.search(output)
    if count_m:
        total, fails = int(count_m.group(1)), int(count_m.group(2))
        test_summary = f"{total - fails}/{total} passed"
    else:
        test_summary = ""

    return {
        "build": "ok" if _BUILD_SUCCEEDED.search(output) else (
                 "fail" if _BUILD_FAILED.search(output) else "unknown"),
        "tests": ("ok" if _TEST_SUCCEEDED.search(output) else (
                  "fail" if _TEST_FAILED_HDR.search(output) else "unknown")),
        "test_summary": test_summary,
        "errors": errors,
        "warnings": warnings,
    }


def parse_swiftlint(output: str) -> dict:
    errors, warnings = [], []
    for m in _SWIFTLINT_DIAG.finditer(output):
        sev = m.group("sev")
        entry = _make(
            "lint_error" if sev == "error" else "lint_warning",
            m.group("file").strip(), int(m.group("line")),
            int(m.group("col")), m.group("msg").strip(),
        )
        (errors if sev == "error" else warnings).append(entry)
    return {
        "lint": "ok" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def parse_ios_full(build_out: str, lint_out: str, test_out: str) -> dict:
    """Merge xcodebuild + swiftlint + test results into one structured report."""
    build  = parse_xcodebuild(build_out)
    lint   = parse_swiftlint(lint_out)
    tests  = parse_xcodebuild(test_out)
    all_errors = build["errors"] + lint["errors"] + tests["errors"]
    return {
        "build":    build["build"],
        "lint":     lint["lint"],
        "tests":    tests["test_summary"] or tests["tests"],
        "errors":   all_errors,
        "warnings": build["warnings"] + lint["warnings"],
        "status":   "pass" if not all_errors else "fail",
    }


def _make(type_: str, file: str, line: int, col: int, msg: str) -> dict:
    return {
        "type": type_, "file": file, "line": line,
        "column": col, "message": msg, "acceptance_criterion": "unknown",
    }
