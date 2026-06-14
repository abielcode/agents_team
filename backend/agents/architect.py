"""
architect.py — Architect agent.
Provider: Ollama / qwen2.5-coder:14b
Roles: sprint review blockers, sprint architecture document.
"""

from __future__ import annotations

import json
from typing import Optional

from .base_agent import BaseAgent


SYSTEM_PROMPT_BASE = """
You are the Architect of an AI-powered development team.
You design the technical structure for each sprint before any code is written.

YOUR RESPONSIBILITIES:
- Review sprint scope and raise any technical blockers or ordering issues
- Produce a comprehensive Sprint Architecture Document for each sprint
- Define all files to create or modify, with their responsibilities and dependencies
- Define protocols/interfaces, data models, and patterns
- Map acceptance criteria to specific code structures
- Maintain consistency with previous sprint architecture documents

YOUR RULES:
- ALWAYS output valid JSON only — no prose outside JSON
- Define EVERY file the Coder will need to touch — nothing implicit
- Prefer protocol-based design for testability
- Flag dependency ordering issues before coding starts
- Reference previous sprint architecture when extending existing code
- ALWAYS check existing_project_files before assigning action to any file:
  * File exists in list → action MUST be "modify"
  * File does not exist → action MUST be "create"
  * Never assign "create" to a file that already exists — this causes duplicate code
- Use the EXACT path from existing_project_files when referencing files to modify

{platform_context}
""".strip()


class ArchitectAgent(BaseAgent):
    name = "architect"
    use_cache = False

    def system_prompt(self, platform_context: Optional[str] = None) -> str:
        ctx = f"\nPLATFORM CONTEXT:\n{platform_context}" if platform_context else ""
        return SYSTEM_PROMPT_BASE.replace("{platform_context}", ctx)

    # ------------------------------------------------------------------ #
    #  Phase 2 — Sprint blocker review                                   #
    # ------------------------------------------------------------------ #

    async def review_sprint_scope(
        self,
        sprint_plan: dict,
        backlog: dict,
        platform_context: str,
        previous_arch: Optional[dict] = None,
    ) -> dict:
        """
        Review proposed sprint scope for technical blockers.
        Output schema:
        {
          "approved": bool,
          "blockers": [
            { "story_id": "US002", "issue": str, "resolution": str }
          ],
          "reordering_needed": bool,
          "suggested_order": ["US001", "US003", "US002"],
          "notes": str
        }
        """
        payload = {
            "action": "review_sprint_scope",
            "sprint_plan": sprint_plan,
            "backlog_stories": [
                s for epic in backlog.get("epics", [])
                for s in epic.get("stories", [])
                if s["id"] in sprint_plan.get("stories", [])
            ],
            "previous_architecture": previous_arch,
            "output_schema": {
                "approved": True,
                "blockers": [],
                "reordering_needed": False,
                "suggested_order": [],
                "notes": "string",
            },
        }
        return await self.run(
            [self.build_message(payload)],
            platform_context=platform_context,
            stream=True,
        )

    # ------------------------------------------------------------------ #
    #  Phase 3 — Sprint Architecture Document                            #
    # ------------------------------------------------------------------ #

    async def create_architecture(
        self,
        sprint_plan: dict,
        backlog: dict,
        platform: str,
        platform_context: str,
        previous_arch: Optional[dict] = None,
        existing_codebase_notes: str = "",
        existing_file_tree: Optional[list] = None,
    ) -> dict:
        """
        Produce the sprint architecture document.
        Output schema per PRD section 3 (Architect):
        {
          "sprint": int,
          "platform": str,
          "pattern": str,
          "epics": [
            {
              "epic_id": str,
              "name": str,
              "story_ids": [str],
              "files": [
                {
                  "path": str,
                  "type": str,
                  "story_id": str,
                  "action": "create|modify",
                  "responsibilities": [str],
                  "dependencies": [str],
                  "acceptance_criteria_coverage": [str]
                }
              ],
              "protocols": [str],
              "data_models": [str],
              "notes": str
            }
          ],
          "build_order": [str],
          "shared_components": [str]
        }
        """
        stories_in_sprint = [
            s for epic in backlog.get("epics", [])
            for s in epic.get("stories", [])
            if s["id"] in sprint_plan.get("stories", [])
        ]

        payload = {
            "action": "create_sprint_architecture",
            "sprint": sprint_plan.get("sprint", 1),
            "platform": platform,
            "stories": stories_in_sprint,
            "previous_architecture": previous_arch,
            "existing_codebase_notes": existing_codebase_notes,
            "existing_project_files": existing_file_tree or [],
            "instruction": (
                "CRITICAL: You MUST check existing_project_files before deciding action for each file. "
                "If a file path already exists in existing_project_files → set action='modify'. "
                "If it does NOT exist → set action='create'. "
                "NEVER mark an existing file as action='create' — that causes duplicate code. "
                "Use exact paths from existing_project_files when referencing files to modify."
            ),
            "output_schema": {
                "sprint": 1,
                "platform": platform,
                "pattern": "MVVM",
                "epics": [
                    {
                        "epic_id": "epic_001",
                        "name": "string",
                        "story_ids": ["US001"],
                        "files": [
                            {
                                "path": "string",
                                "type": "string",
                                "story_id": "US001",
                                "action": "create",
                                "responsibilities": ["string"],
                                "dependencies": ["string"],
                                "acceptance_criteria_coverage": ["AC1"],
                            }
                        ],
                        "protocols": ["string"],
                        "data_models": ["string"],
                        "notes": "string",
                    }
                ],
                "build_order": ["string"],
                "shared_components": ["string"],
            },
        }
        return await self.run(
            [self.build_message(payload)],
            platform_context=platform_context,
            stream=True,
        )
