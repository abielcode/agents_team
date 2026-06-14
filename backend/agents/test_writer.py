"""
test_writer.py — Test Writer agent.
Provider: Ollama / qwen2.5-coder:14b
Role: Write tests after Coder completes each story. Every test maps to an AC.
"""

from __future__ import annotations

from typing import Optional

from .base_agent import BaseAgent


SYSTEM_PROMPT_BASE = """
You are the Test Writer of an AI-powered development team.
You write tests AFTER the Coder has implemented each user story.

YOUR RULES:
- Write tests for EVERY acceptance criterion — no AC should be uncovered
- Label each test with which AC it covers (in a // AC1: comment above each test)
- Write unit tests for logic, ViewModels, services
- Follow platform test conventions STRICTLY
- Tests must be complete and runnable — no stubs

OUTPUT FORMAT — use EXACTLY this delimiter format (do NOT use JSON for file contents):

METADATA:{"story_id": "US001"}
===FILE: ShowSpotTests/CartViewModelTests.swift===
import Testing
@testable import ShowSpot

// AC1: segment switcher displays options
@Test func testSegmentSwitcherDisplaysOptions() { ... }
===END FILE===

Write raw Swift code between the delimiters. Do NOT escape anything.

{platform_context}
""".strip()


class TestWriterAgent(BaseAgent):
    name = "test_writer"
    use_cache = False

    def system_prompt(self, platform_context: Optional[str] = None) -> str:
        ctx = f"\nPLATFORM CONTEXT:\n{platform_context}" if platform_context else ""
        return SYSTEM_PROMPT_BASE.replace("{platform_context}", ctx)

    async def write_tests(
        self,
        story: dict,
        implemented_files: list[dict],
        platform: str,
        platform_context: str,
        test_framework_description: str,
    ) -> dict:
        """
        Write tests for a completed story.
        implemented_files: list of { path, content } from Coder output.
        """
        payload = {
            "action": "write_tests",
            "story": story,
            "implemented_files": implemented_files,
            "platform": platform,
            "test_framework": test_framework_description,
            "instruction": (
                "Write tests covering EVERY acceptance criterion. "
                "Each test must have a comment indicating which AC it covers. "
                "Include the AC identifiers in the 'covers' array of each test file."
            ),
            "output_schema": {
                "story_id": story["id"],
                "test_files": [
                    {
                        "path": "string",
                        "content": "string",
                        "covers": ["AC1"],
                    }
                ],
            },
        }

        return await self.run_multifile(
            [self.build_message(payload)],
            platform_context=platform_context,
            story_id=story["id"],
        )
