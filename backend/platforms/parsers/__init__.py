from .xcodebuild_parser import parse_ios_full, parse_xcodebuild, parse_swiftlint
from .gradle_parser import parse_android_full, parse_gradle, parse_ktlint, parse_gradle_tests
from .pytest_parser import parse_django_full, parse_pytest, parse_flake8, parse_mypy

__all__ = [
    "parse_ios_full", "parse_xcodebuild", "parse_swiftlint",
    "parse_android_full", "parse_gradle", "parse_ktlint", "parse_gradle_tests",
    "parse_django_full", "parse_pytest", "parse_flake8", "parse_mypy",
]


def parse_full(platform: str, build_out: str, lint_out: str, test_out: str) -> dict:
    """Dispatch to the correct platform parser."""
    if platform == "ios":
        return parse_ios_full(build_out, lint_out, test_out)
    elif platform == "android":
        return parse_android_full(build_out, lint_out, test_out)
    elif platform == "django":
        return parse_django_full(build_out, lint_out, test_out)
    else:
        raise ValueError(f"Unknown platform: {platform}")
