"""
verifier.py — Verifier agent.
Provider: Ollama / qwen2.5-coder:7b
Role: Run build/lint/test, parse results with platform-aware parsers,
map failures to ACs via LLM, produce structured retry report.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from .base_agent import BaseAgent
from ..platforms.parsers import parse_full


SYSTEM_PROMPT = """
You are the Verifier of an AI-powered development team.
You receive pre-parsed build, lint, and test errors and must:
1. Map each error to the acceptance criterion it violates (use "unknown" if not clear)
2. Produce a concise retry_instruction for the Coder
3. Output valid JSON only

PASS OUTPUT:
{
  "story_id": "US001",
  "status": "pass",
  "build": "ok",
  "lint": "ok",
  "tests": "N/N passed",
  "acceptance_criteria": { "AC1": "pass", "AC2": "pass" }
}

FAIL OUTPUT:
{
  "story_id": "US001",
  "status": "fail",
  "build": "ok|fail",
  "lint": "ok|fail",
  "tests": "N/M passed",
  "errors": [
    {
      "type": "build_error|lint_error|lint_warning|test_failure|test_error",
      "file": "path/to/file",
      "line": 0,
      "message": "string",
      "acceptance_criterion": "AC1|unknown"
    }
  ],
  "acceptance_criteria": { "AC1": "pass|fail", "AC2": "fail" },
  "retry_instruction": "Concise, specific fix instruction for the Coder"
}
""".strip()


class VerifierAgent(BaseAgent):
    name = "verifier"
    use_cache = False

    def system_prompt(self, platform_context: Optional[str] = None) -> str:
        return SYSTEM_PROMPT

    # ------------------------------------------------------------------ #
    #  Shell execution                                                    #
    # ------------------------------------------------------------------ #

    async def _run_command(self, cmd: str, cwd: str, timeout: int = 300) -> tuple[int, str]:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                return 1, f"Command timed out after {timeout}s: {cmd}"
            return proc.returncode, stdout.decode(errors="replace")
        except Exception as e:
            return 1, f"Command execution error: {e}"

    # ------------------------------------------------------------------ #
    #  Main verification flow                                             #
    # ------------------------------------------------------------------ #

    async def verify_story(
        self,
        story: dict,
        acceptance_criteria: list[str],
        project_path: str,
        platform: str,
        build_cmd: str,
        test_cmd: str,
        lint_cmd: str,
    ) -> dict:
        """
        1. Run build/lint/test shell commands
        2. Parse output with platform-specific parsers (no LLM tokens wasted)
        3. If errors found, send only the structured errors to LLM for AC mapping
        4. Return structured pass/fail report
        """
        story_id = story["id"]
        print(f"\n[VERIFIER] Running verification for {story_id} ({platform})")

        # ── Run tools ──────────────────────────────────────────────────
        print(f"  → Build...")
        build_rc, build_out = await self._run_command(build_cmd, project_path)
        print(f"  {'✓' if build_rc == 0 else '✗'} Build {'passed' if build_rc == 0 else 'FAILED'}")

        print(f"  → Lint...")
        lint_tool = lint_cmd.split()[0]
        import shutil
        if shutil.which(lint_tool) is None:
            print(f"  ⚠ Lint skipped ({lint_tool} not installed)")
            lint_rc, lint_out = 0, ""
        else:
            lint_rc, lint_out = await self._run_command(lint_cmd, project_path)
            print(f"  {'✓' if lint_rc == 0 else '✗'} Lint {'passed' if lint_rc == 0 else 'FAILED'}")

        test_out = "Skipped — build failed"
        test_rc = 1
        if build_rc == 0:
            print(f"  → Tests...")
            test_rc, test_out = await self._run_command(test_cmd, project_path)
            print(f"  {'✓' if test_rc == 0 else '✗'} Tests {'passed' if test_rc == 0 else 'FAILED'}")

        # ── Parse with platform-aware parsers ─────────────────────────
        parsed = parse_full(platform, build_out, lint_out, test_out)

        # Override parser status with actual exit codes
        if build_rc != 0 and parsed["build"] == "unknown":
            parsed["build"] = "fail"
        if lint_rc != 0 and parsed["lint"] == "unknown":
            parsed["lint"] = "fail"
        if (build_rc != 0 or lint_rc != 0) and not parsed["errors"]:
            # Commands failed but parser found no structured errors — add raw output as error
            if build_rc != 0:
                parsed["errors"].append({
                    "type": "build_error", "file": "", "line": 0,
                    "message": build_out[-500:].strip() or "Build command failed",
                    "acceptance_criterion": "unknown"
                })
            if lint_rc != 0:
                parsed["errors"].append({
                    "type": "lint_error", "file": "", "line": 0,
                    "message": lint_out[-300:].strip() or "Lint command failed",
                    "acceptance_criterion": "unknown"
                })
            parsed["status"] = "fail"

        # ── Fast-path: no errors → pass without LLM call ──────────────
        if not parsed["errors"] and parsed["status"] == "pass":
            print(f"  ✅ {story_id} — all checks passed (no LLM call needed)")
            return {
                "story_id": story_id,
                "status": "pass",
                "build": parsed["build"],
                "lint": parsed["lint"],
                "tests": parsed["tests"],
                "acceptance_criteria": {
                    ac.split(":")[0].strip(): "pass"
                    for ac in acceptance_criteria
                },
            }

        # ── LLM: map errors to acceptance criteria ─────────────────────
        payload = {
            "action": "map_errors_to_acceptance_criteria",
            "story_id": story_id,
            "acceptance_criteria": acceptance_criteria,
            "parsed_result": {
                "build": parsed["build"],
                "lint": parsed["lint"],
                "tests": parsed["tests"],
                "errors": parsed["errors"][:20],  # cap to save tokens
                "warnings": parsed.get("warnings", [])[:5],
            },
            "instruction": (
                "For each error, identify which acceptance criterion it violates. "
                "Set acceptance_criterion to the AC identifier (e.g. 'AC1') or 'unknown'. "
                "Write a single concise retry_instruction summarising what the Coder must fix."
            ),
        }

        result = await self.run(
            [self.build_message(payload)],
            story_id=story_id,
            stream=False,
        )

        # Ensure status is set
        if "status" not in result:
            result["status"] = "fail" if parsed["errors"] else "pass"
        result["story_id"] = story_id

        return result

    # ------------------------------------------------------------------ #
    #  Dry-run                                                            #
    # ------------------------------------------------------------------ #

    async def dry_verify(
        self,
        story: dict,
        implemented_files: list[dict],
        platform: str = "ios",
    ) -> dict:
        """
        LLM-only code review — used when no real project path is available.
        Uses platform-specific checklist (ARC, memory safety, opaque types, concurrency).
        """
        story_id = story["id"]

        # Load platform checklist if available
        checklist = ""
        try:
            from ..platforms.base import get_platform
            plat = get_platform(platform)
            if hasattr(plat, "code_review_checklist"):
                checklist = plat.code_review_checklist()
        except Exception:
            pass

        payload = {
            "action": "dry_verify",
            "story_id": story_id,
            "story": story,
            "implemented_files": implemented_files,
            "platform": platform,
            "instruction": (
                "Review the implemented files thoroughly as a senior iOS engineer would. "
                "Check: (1) every acceptance criterion is addressed, "
                "(2) all items in the CODE REVIEW CHECKLIST below — flag any violation as an error, "
                "(3) Swift concurrency correctness (ARC, memory safety, opaque types). "
                "This is a dry run — no build tools. Be strict and specific."
            ),
            "code_review_checklist": checklist,
        }
        return await self.run(
            [self.build_message(payload)],
            story_id=story_id,
            stream=False,
        )
