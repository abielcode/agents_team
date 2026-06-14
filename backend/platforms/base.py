"""
base.py — Platform context interface.
All platform packs implement PlatformContext.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VerifierTools:
    build_cmd: str
    test_cmd: str
    lint_cmd: str
    lint_fix_cmd: str


class PlatformContext(ABC):
    name: str

    @abstractmethod
    def system_prompt_context(self) -> str:
        """Platform-specific context block injected into agent system prompts."""

    @abstractmethod
    def verifier_tools(self) -> VerifierTools:
        """Shell commands the Verifier agent should run."""

    @abstractmethod
    def test_framework_description(self) -> str:
        """Short description of test frameworks for Test Writer prompt."""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "context": self.system_prompt_context(),
            "verifier_tools": {
                "build": self.verifier_tools().build_cmd,
                "test": self.verifier_tools().test_cmd,
                "lint": self.verifier_tools().lint_cmd,
            },
            "test_frameworks": self.test_framework_description(),
        }


def get_platform(name: str) -> PlatformContext:
    from .ios import IOSPlatform
    from .android import AndroidPlatform
    from .django import DjangoPlatform

    platforms = {
        "ios": IOSPlatform,
        "android": AndroidPlatform,
        "django": DjangoPlatform,
    }
    key = name.lower()
    if key not in platforms:
        raise ValueError(
            f"Unknown platform '{name}'. Choose from: {list(platforms.keys())}"
        )
    return platforms[key]()
