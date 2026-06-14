"""
orchestrator.py — Orchestrator agent.
Provider: Anthropic / claude-haiku-4-5-20251001
Roles: PRD refinement, backlog creation, sprint planning, sprint review.
Never writes code. JSON output only. Called at phase transitions only.
"""

from __future__ import annotations

import json
from typing import Optional

from .base_agent import BaseAgent


SYSTEM_PROMPT = """
You are the Orchestrator of an AI-powered development team.
You manage the agile development lifecycle for software projects.

YOUR RESPONSIBILITIES:
- Refine raw human input into a structured Product Requirements Document (PRD)
- Convert an approved PRD into a full product backlog (epics + user stories)
- Propose sprint scope and sequencing based on dependencies and complexity
- Produce sprint review summaries and propose the next sprint scope

YOUR RULES:
- NEVER write code, tests, or architecture documents
- ALWAYS output valid JSON only — no prose, no markdown, no explanation outside JSON
- Keep output compact — no unnecessary whitespace in keys
- Respect dependencies: foundational stories always come before dependent ones
- Sprint scope: group tightly-coupled stories together, avoid splitting dependencies across sprints
- Story points: 1=trivial, 2=small, 3=medium, 5=large, 8=very large, 13=epic (split it)

OUTPUT SCHEMAS are provided in each user message. Follow them exactly.
""".strip()


class OrchestratorAgent(BaseAgent):
    name = "orchestrator"
    use_cache = True  # System prompt cached via Anthropic prompt caching

    def system_prompt(self, platform_context: Optional[str] = None) -> str:
        return SYSTEM_PROMPT

    # ------------------------------------------------------------------ #
    #  Phase 0 — PRD Refinement                                          #
    # ------------------------------------------------------------------ #

    async def refine_prd(self, raw_input: str, platform: str) -> dict:
        """
        Takes free-form human description and returns a structured PRD.
        Output schema:
        {
          "product_overview": str,
          "goals": [str],
          "success_metrics": [str],
          "features": [
            {
              "name": str,
              "description": str,
              "user_stories": [
                {
                  "id": str,        # "US001"
                  "title": str,
                  "as_a": str,
                  "i_want": str,
                  "so_that": str,
                  "acceptance_criteria": [str]
                }
              ]
            }
          ],
          "technical_constraints": [str],
          "platform": str
        }
        """
        payload = {
            "action": "refine_prd",
            "platform": platform,
            "raw_input": raw_input,
            "output_schema": {
                "product_overview": "string",
                "goals": ["string"],
                "success_metrics": ["string"],
                "features": [
                    {
                        "name": "string",
                        "description": "string",
                        "user_stories": [
                            {
                                "id": "US001",
                                "title": "string",
                                "as_a": "string",
                                "i_want": "string",
                                "so_that": "string",
                                "acceptance_criteria": ["string"],
                            }
                        ],
                    }
                ],
                "technical_constraints": ["string"],
                "platform": "string",
            },
        }
        return await self.run([self.build_message(payload)], stream=True)

    # ------------------------------------------------------------------ #
    #  Phase 1 — Backlog Creation                                        #
    # ------------------------------------------------------------------ #

    async def create_backlog(self, prd: dict) -> dict:
        """
        Converts approved PRD into full product backlog.
        Output schema:
        {
          "epics": [
            {
              "id": "epic_001",
              "name": str,
              "description": str,
              "stories": [
                {
                  "id": "US001",
                  "epic_id": "epic_001",
                  "title": str,
                  "description": str,
                  "acceptance_criteria": [str],
                  "story_points": int,
                  "depends_on": ["US000"],
                  "platform_notes": str
                }
              ]
            }
          ]
        }
        """
        payload = {
            "action": "create_backlog",
            "prd": prd,
            "output_schema": {
                "epics": [
                    {
                        "id": "epic_001",
                        "name": "string",
                        "description": "string",
                        "stories": [
                            {
                                "id": "US001",
                                "epic_id": "epic_001",
                                "title": "string",
                                "description": "string",
                                "acceptance_criteria": ["string"],
                                "story_points": 3,
                                "depends_on": [],
                                "platform_notes": "string",
                            }
                        ],
                    }
                ]
            },
        }
        return await self.run([self.build_message(payload)], stream=True)

    # ------------------------------------------------------------------ #
    #  Phase 2 — Sprint Planning                                         #
    # ------------------------------------------------------------------ #

    async def plan_sprint(self, backlog: dict, sprint_number: int, completed_story_ids: list[str]) -> dict:
        """
        Proposes sprint scope from remaining backlog.
        Output schema:
        {
          "sprint": int,
          "stories": ["US001", "US002"],
          "rationale": str,
          "estimated_points": int,
          "dependencies_resolved": bool
        }
        """
        payload = {
            "action": "plan_sprint",
            "sprint_number": sprint_number,
            "completed_story_ids": completed_story_ids,
            "backlog": backlog,
            "instructions": (
                "Select stories for this sprint. "
                "Prioritize: foundational stories first, no story with unresolved depends_on, "
                "aim for 20-30 story points per sprint. "
                "Group tightly-coupled stories together."
            ),
            "output_schema": {
                "sprint": sprint_number,
                "stories": ["US001"],
                "rationale": "string",
                "estimated_points": 0,
                "dependencies_resolved": True,
            },
        }
        return await self.run([self.build_message(payload)], stream=True)

    # ------------------------------------------------------------------ #
    #  Phase 5 — Sprint Review                                           #
    # ------------------------------------------------------------------ #

    async def review_sprint(
        self,
        sprint_number: int,
        completed_stories: list[dict],
        flagged_stories: list[dict],
        files_changed: list[str],
        cost_summary: dict,
        backlog: dict,
    ) -> dict:
        """
        Produces sprint summary and proposes next sprint.
        Output schema:
        {
          "sprint": int,
          "summary": str,
          "completed": ["US001"],
          "flagged": [{"id": "US002", "reason": str}],
          "files_created": [str],
          "files_modified": [str],
          "cost": { ...cost_summary... },
          "next_sprint_proposal": { ...same as plan_sprint output... }
        }
        """
        payload = {
            "action": "review_sprint",
            "sprint_number": sprint_number,
            "completed_stories": completed_stories,
            "flagged_stories": flagged_stories,
            "files_changed": files_changed,
            "cost_summary": cost_summary,
            "remaining_backlog": backlog,
            "output_schema": {
                "sprint": sprint_number,
                "summary": "string",
                "completed": ["US001"],
                "flagged": [{"id": "US002", "reason": "string"}],
                "files_created": ["string"],
                "files_modified": ["string"],
                "cost": {},
                "next_sprint_proposal": {
                    "sprint": sprint_number + 1,
                    "stories": [],
                    "rationale": "string",
                    "estimated_points": 0,
                },
            },
        }
        return await self.run([self.build_message(payload)], stream=True)
