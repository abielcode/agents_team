"""
coder.py — Coder agent.
Provider: Ollama / qwen2.5-coder:14b
Role: Implement one user story at a time. Production-ready code only.
On retry: fix only the specific Verifier errors.
"""

from __future__ import annotations

import json
from typing import Optional

from .base_agent import BaseAgent


SYSTEM_PROMPT_BASE = """
You are the Coder of an AI-powered development team.
You write production-ready code implementing one user story at a time.

YOUR RULES:
- Read the sprint architecture document before writing any code
- Read existing file contents before modifying them — never overwrite blindly
- Write COMPLETE files — no stubs, no TODOs, no placeholder comments
- Follow platform conventions STRICTLY as defined in the architecture document
- On retry: fix ONLY the specific issues listed in verifier_feedback — do not rewrite passing files
- Never rewrite a file that already passed verification
- CRITICAL FILE PATHS: Always use the EXACT folder structure from the EXISTING CODEBASE CONTEXT.
  * NEVER create files at the project root — always inside the correct subfolder (e.g. ShowSpot/)
  * Match the existing Scenes/ViewModels/Services folder structure exactly as described in codebase context
  * If codebase uses ShowSpot/Scenes/FeatureName/ViewModels/Foo.swift — use that exact pattern
- EXISTING FILES: You will receive the actual contents of key project files in `existing_files`.
  * Read them carefully before writing anything
  * When modifying a file, output the COMPLETE modified file — not just the changed parts
  * NEVER duplicate types, enums, or classes that already exist in those files
  * If `CartViewModel` already exists in existing_files, modify it — do not create a new one
  * If `OrderMode` enum already exists, reuse it — do not redefine it

OUTPUT FORMAT — use EXACTLY this delimiter format (do NOT use JSON for file contents):

METADATA:{"story_id": "US001", "notes": "Brief implementation notes"}
===FILE: ShowSpot/Scenes/Cart/ViewModels/CartViewModel.swift===
import Foundation
// ... complete file content, no escaping needed ...
===END FILE===
===FILE: ShowSpot/Scenes/Cart/Views/CartView.swift===
import SwiftUI
// ... complete file content ...
===END FILE===

IMPORTANT: Write raw source code between the delimiters. Do NOT escape anything.
Every file must be complete — no stubs, no TODOs.

{platform_context}
""".strip()


class CoderAgent(BaseAgent):
    name = "coder"
    use_cache = False

    def system_prompt(self, platform_context: Optional[str] = None) -> str:
        ctx = f"\nPLATFORM CONTEXT:\n{platform_context}" if platform_context else ""
        return SYSTEM_PROMPT_BASE.replace("{platform_context}", ctx)

    async def implement_story(
        self,
        story: dict,
        architecture: dict,
        platform_context: str,
        existing_files: Optional[list[dict]] = None,
        verifier_feedback: Optional[dict] = None,
        retry_count: int = 0,
    ) -> dict:
        """
        Implement a user story. On retry, verifier_feedback contains specific errors.

        Input shape per PRD section 3 (Coder):
        {
          "story": { id, title, description, acceptance_criteria },
          "architecture": { ...epic blueprint for this story... },
          "existing_files": [ { path, content } ],
          "verifier_feedback": null | { errors: [...], retry_instruction: str }
        }
        """
        # Find the epic architecture relevant to this story
        story_id = story["id"]
        relevant_epic = None
        for epic in architecture.get("epics", []):
            if story_id in epic.get("story_ids", []):
                relevant_epic = epic
                break

        payload: dict = {
            "action": "implement_story",
            "retry_count": retry_count,
            "story": story,
            "epic_architecture": relevant_epic,
            "build_order": architecture.get("build_order", []),
        }

        if existing_files:
            payload["existing_files"] = existing_files

        if verifier_feedback:
            payload["verifier_feedback"] = verifier_feedback
            payload["instruction"] = (
                "This is a RETRY. Fix ONLY the specific errors listed in "
                "verifier_feedback. Do not rewrite files that are not mentioned."
            )
        else:
            payload["instruction"] = (
                "Implement this story completely. Follow the epic_architecture exactly. "
                "Write complete file contents — no stubs or TODOs."
            )

        return await self.run_multifile(
            [self.build_message(payload)],
            platform_context=platform_context,
            story_id=story_id,
        )
