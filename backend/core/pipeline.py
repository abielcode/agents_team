"""
pipeline.py — Sprint execution engine.
Orchestrates the full lifecycle per PRD section 2:
INIT → PLANNING → ARCHITECTURE → CODING → TESTING → VERIFYING → DONE / retry
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from .gateway import Gateway
from .cost_tracker import CostTracker, CostGuardError
from .reporter import Reporter, CLI_REPORTER
from ..agents import (
    OrchestratorAgent,
    ArchitectAgent,
    CoderAgent,
    TestWriterAgent,
    VerifierAgent,
)
from ..platforms.base import get_platform, PlatformContext
from ..tools.codebase_scanner import CodebaseScanner
from ..tools.git_guard import GitGuard, GitGuardError
from ..tools.xcodegen_sync import XcodegenSync


class Phase(str, Enum):
    INIT = "INIT"
    PLANNING = "PLANNING"
    ARCHITECTURE = "ARCHITECTURE"
    CODING = "CODING"
    TESTING = "TESTING"
    VERIFYING = "VERIFYING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class StoryResult:
    story_id: str
    status: str          # "done" | "flagged"
    retry_count: int = 0
    flag_reason: Optional[str] = None
    files_written: list[str] = field(default_factory=list)
    verifier_report: Optional[dict] = None


@dataclass
class SprintResult:
    sprint_number: int
    story_results: list[StoryResult] = field(default_factory=list)
    architecture: Optional[dict] = None
    review: Optional[dict] = None
    cost: Optional[dict] = None

    @property
    def completed(self) -> list[StoryResult]:
        return [r for r in self.story_results if r.status == "done"]

    @property
    def flagged(self) -> list[StoryResult]:
        return [r for r in self.story_results if r.status == "flagged"]

    @property
    def all_files_written(self) -> list[str]:
        return [f for r in self.story_results for f in r.files_written]


class Pipeline:
    """
    Sprint execution engine.
    Instantiate once per sprint run.
    """

    MAX_RETRIES = 3

    def __init__(
        self,
        config: dict,
        project_path: str,
        platform_name: str,
        sprint_number: int = 1,
        dry_run: bool = False,
        git_safe: bool = False,
        skip_scan: bool = False,
        reporter: Optional[Reporter] = None,
    ):
        self.config = config
        self.project_path = Path(project_path)
        self.platform_name = platform_name
        self.sprint_number = sprint_number
        self.dry_run = dry_run
        self.git_safe = git_safe
        self.skip_scan = skip_scan
        self.reporter = reporter or CLI_REPORTER

        self.platform: PlatformContext = get_platform(platform_name)
        self.platform_context_str = self.platform.system_prompt_context()
        self.verifier_tools = self.platform.verifier_tools()

        self.cost_tracker = CostTracker(config, sprint_number)
        self.gateway = Gateway(config)

        self.orchestrator = OrchestratorAgent(self.gateway, self.cost_tracker, self.reporter)
        self.architect    = ArchitectAgent(self.gateway, self.cost_tracker, self.reporter)
        self.coder        = CoderAgent(self.gateway, self.cost_tracker, self.reporter)
        self.test_writer  = TestWriterAgent(self.gateway, self.cost_tracker, self.reporter)
        self.verifier     = VerifierAgent(self.gateway, self.cost_tracker, self.reporter)

        # Tools
        self.git_guard = GitGuard(str(self.project_path), safe_mode=git_safe)
        self.xcodegen = XcodegenSync(str(self.project_path)) if platform_name == "ios" else None
        self._codebase_context: Optional[str] = None  # filled during INIT

    # ------------------------------------------------------------------ #
    #  Entry point: run a full sprint                                     #
    # ------------------------------------------------------------------ #

    async def run_sprint(
        self,
        task_description: str,
        prd: Optional[dict] = None,
        backlog: Optional[dict] = None,
        sprint_plan: Optional[dict] = None,
        previous_architecture: Optional[dict] = None,
        completed_story_ids: Optional[list[str]] = None,
    ) -> SprintResult:
        result = SprintResult(sprint_number=self.sprint_number)
        completed_ids = completed_story_ids or []

        self._print_phase(Phase.INIT)

        # ── Git safety check ─────────────────────────────────────────────
        try:
            self.git_guard.check()  # planned_writes unknown yet — warn on any dirty state
        except GitGuardError as e:
            print(str(e))
            raise

        # ── Codebase scan (fills gaps in CODEBASE.md) ────────────────────
        if not self.skip_scan:
            self._print_phase(Phase.INIT, "Codebase Scan")
            scanner = CodebaseScanner(str(self.project_path))
            ctx = scanner.scan()
            self._codebase_context = ctx.to_prompt_str()
            # Always inject codebase context into platform context
            if self._codebase_context:
                self.platform_context_str = (
                    self.platform.system_prompt_context()
                    + "\n\n"
                    + self._codebase_context
                )

        try:
            # ── Phase 0+1: PRD + Backlog (if not provided) ──────────────
            if prd is None:
                self._print_phase(Phase.PLANNING, "PRD Refinement")
                prd = await self.orchestrator.refine_prd(task_description, self.platform_name)
                self._save_artifact("prd.json", prd)

            if backlog is None:
                self._print_phase(Phase.PLANNING, "Backlog Creation")
                backlog = await self.orchestrator.create_backlog(prd)
                self._save_artifact("backlog.json", backlog)

            # ── Phase 2: Sprint Planning ─────────────────────────────────
            if sprint_plan is None:
                self._print_phase(Phase.PLANNING, "Sprint Planning")
                sprint_plan = await self.orchestrator.plan_sprint(
                    backlog, self.sprint_number, completed_ids
                )
                self._save_artifact(f"sprint_{self.sprint_number}_plan.json", sprint_plan)

            # ── Phase 2b: Architect scope review ────────────────────────
            self._print_phase(Phase.PLANNING, "Architect Review")
            try:
                scope_review = await self.architect.review_sprint_scope(
                    sprint_plan, backlog, self.platform_context_str, previous_architecture
                )
                if not scope_review.get("approved", True):
                    print("\n[ARCHITECT] Blockers found:")
                    for b in scope_review.get("blockers", []):
                        print(f"  ⚠ {b['story_id']}: {b['issue']}")
                        print(f"    Resolution: {b['resolution']}")
            except Exception as e:
                print(f"\n[ARCHITECT] Scope review failed ({e}), proceeding with default story order")
                scope_review = {}

            # Respect suggested ordering from architect
            story_order = scope_review.get("suggested_order") or sprint_plan.get("stories", [])

            # ── Phase 3: Architecture document ──────────────────────────
            self._print_phase(Phase.ARCHITECTURE)
            try:
                architecture = await self.architect.create_architecture(
                    sprint_plan,
                    backlog,
                    self.platform_name,
                    self.platform_context_str,
                    previous_architecture,
                    existing_codebase_notes=self._read_codebase_notes(),
                    existing_file_tree=self._scan_project_files(),
                )
            except Exception as e:
                print(f"\n[ARCHITECT] Architecture generation failed ({e}), continuing without architecture doc")
                architecture = {}
            result.architecture = architecture
            self._save_artifact(f"sprint_{self.sprint_number}_architecture.json", architecture)

            # Build story lookup
            story_map = {
                s["id"]: s
                for epic in backlog.get("epics", [])
                for s in epic.get("stories", [])
            }

            # ── Phase 4: Development loop ────────────────────────────────
            for story_id in story_order:
                story = story_map.get(story_id)
                if story is None:
                    print(f"\n[PIPELINE] Warning: story {story_id} not found in backlog, skipping")
                    continue

                story_result = await self._run_story(story, architecture)
                result.story_results.append(story_result)

            # ── Phase 5: Sprint Review ───────────────────────────────────
            self._print_phase(Phase.DONE, "Sprint Review")
            completed_stories = [story_map[r.story_id] for r in result.completed if r.story_id in story_map]
            flagged_stories = [
                {"id": r.story_id, "reason": r.flag_reason}
                for r in result.flagged
            ]

            cost_summary = self.cost_tracker.to_dict()
            result.cost = cost_summary

            review = await self.orchestrator.review_sprint(
                self.sprint_number,
                completed_stories,
                flagged_stories,
                result.all_files_written,
                cost_summary,
                backlog,
            )
            result.review = review
            self._save_artifact(f"sprint_{self.sprint_number}_review.json", review)

            self.cost_tracker.print_summary()
            self._print_sprint_summary(result)

        except CostGuardError as e:
            print(f"\n[PIPELINE] Cost guard triggered — sprint halted: {e}")
            result.story_results.append(
                StoryResult(story_id="__cost_guard__", status="flagged", flag_reason=str(e))
            )

        return result

    # ------------------------------------------------------------------ #
    #  Per-story development loop                                         #
    # ------------------------------------------------------------------ #

    async def _run_story(self, story: dict, architecture: dict) -> StoryResult:
        story_id = story["id"]
        self.reporter.log(f"STORY: {story_id} — {story['title']}")

        result = StoryResult(story_id=story_id, status="flagged")
        verifier_feedback: Optional[dict] = None
        coder_output: Optional[dict] = None

        for attempt in range(self.MAX_RETRIES + 1):
            if attempt > 0:
                self.reporter.log(f"Retry {attempt}/{self.MAX_RETRIES} for {story_id}", level="warn")

            # ── CODING ──────────────────────────────────────────────────
            self._print_phase(Phase.CODING, story_id)
            existing_files = self._read_existing_files(story, architecture)

            try:
                coder_output = await self.coder.implement_story(
                    story=story,
                    architecture=architecture,
                    platform_context=self.platform_context_str,
                    existing_files=existing_files,
                    verifier_feedback=verifier_feedback,
                    retry_count=attempt,
                )
            except Exception as e:
                self.reporter.log(f"Coder error: {e}", level="error")
                result.flag_reason = f"Coder error: {e}"
                break

            # Write files to project
            written = self._write_files(coder_output.get("files", []))
            result.files_written.extend(written)

            # ── Git safety re-check on written files ─────────────────────
            if written:
                self.git_guard.check(planned_writes=written)

            # ── Xcodegen sync (iOS only) ──────────────────────────────────
            # Disabled — pbxproj patching corrupts the project file.
            # Files are written to disk; drag them into Xcode manually or
            # run `xcodegen generate` with a project.yml after the sprint.
            # if self.xcodegen and written and not self.dry_run:
            #     self.xcodegen.sync(written)

            # ── TESTING ─────────────────────────────────────────────────
            self._print_phase(Phase.TESTING, story_id)
            implemented_files = coder_output.get("files", [])

            try:
                test_output = await self.test_writer.write_tests(
                    story=story,
                    implemented_files=implemented_files,
                    platform=self.platform_name,
                    platform_context=self.platform_context_str,
                    test_framework_description=self.platform.test_framework_description(),
                )
                test_files_written = self._write_files(test_output.get("files", test_output.get("test_files", [])))
                result.files_written.extend(test_files_written)
            except Exception as e:
                self.reporter.log(f"Test Writer error: {e}", level="warn")
                # Non-fatal — continue to verification

            # ── VERIFYING ───────────────────────────────────────────────
            self._print_phase(Phase.VERIFYING, story_id)

            try:
                if self.dry_run:
                    verification = await self.verifier.dry_verify(story, implemented_files, platform=self.platform_name)
                else:
                    verification = await self.verifier.verify_story(
                        story=story,
                        acceptance_criteria=story.get("acceptance_criteria", []),
                        project_path=str(self.project_path),
                        platform=self.platform_name,
                        build_cmd=self.verifier_tools.build_cmd,
                        test_cmd=self.verifier_tools.test_cmd,
                        lint_cmd=self.verifier_tools.lint_cmd,
                    )
            except Exception as e:
                self.reporter.log(f"Verifier error: {e}", level="error")
                result.flag_reason = f"Verifier error: {e}"
                break

            result.verifier_report = verification

            if verification.get("status") == "pass":
                result.status = "done"
                result.retry_count = attempt
                self.reporter.story_status(story_id, "done", attempt)
                break
            else:
                errors = verification.get("errors", [])
                self.reporter.log(
                    f"{story_id} FAILED — {len(errors)} error(s)", level="warn"
                )
                for err in errors[:3]:
                    self.reporter.log(
                        f"[{err.get('type','?')}] {err.get('file','')}:{err.get('line','')} — {err.get('message','')[:80]}",
                        level="warn",
                    )

                verifier_feedback = verification

                if attempt == self.MAX_RETRIES:
                    result.status = "flagged"
                    result.flag_reason = (
                        f"Failed after {self.MAX_RETRIES} retries. "
                        f"Last error: {verification.get('retry_instruction', 'See verifier report')}"
                    )
                    self.reporter.story_status(
                        story_id, "flagged", attempt, result.flag_reason
                    )

        return result

    # ------------------------------------------------------------------ #
    #  File I/O                                                           #
    # ------------------------------------------------------------------ #

    def _write_files(self, files: list[dict]) -> list[str]:
        """Write coder/test output files to the target project. Returns list of paths written."""
        written = []
        for f in files:
            rel_path = f.get("path", "")
            content = f.get("content", "")
            if not rel_path or not content:
                continue

            abs_path = self.project_path / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)

            mode = "w" if f.get("action", "create") in ("create", "modify") else "w"
            with open(abs_path, mode, encoding="utf-8") as fh:
                fh.write(content)

            self.reporter.log(f"wrote: {rel_path}")
            written.append(rel_path)
        return written

    def _read_existing_files(self, story: dict, architecture: dict) -> list[dict]:
        """
        Read existing files relevant to this story from the project.
        Always reads key files that stories commonly modify, plus any files
        the architect marked as 'modify'.
        """
        story_id = story["id"]
        existing = []
        seen_paths = set()

        def _read(rel_path: str):
            if rel_path in seen_paths:
                return
            seen_paths.add(rel_path)
            abs_path = self.project_path / rel_path
            if abs_path.exists():
                try:
                    content = abs_path.read_text(encoding="utf-8")
                    existing.append({"path": rel_path, "content": content})
                except Exception:
                    pass

        # Always read files architect marked as modify
        for epic in architecture.get("epics", []):
            if story_id not in epic.get("story_ids", []):
                continue
            for file_spec in epic.get("files", []):
                if file_spec.get("action") == "modify":
                    _read(file_spec["path"])

        return existing

    def _scan_project_files(self) -> list[str]:
        """Return sorted list of all source files in the project, relative to project root."""
        skip_dirs = {".git", ".build", "DerivedData", "Pods", ".swiftpm",
                     "node_modules", "__pycache__", ".venv", "build", "dist", ".agents_team"}
        skip_exts = {".pyc", ".o", ".a", ".dylib", ".png", ".jpg", ".jpeg",
                     ".pdf", ".xcassets", ".storyboard", ".xib"}
        files = []
        for path in self.project_path.rglob("*"):
            if path.is_dir():
                continue
            if any(skip in path.parts for skip in skip_dirs):
                continue
            if path.suffix in skip_exts:
                continue
            if path.suffix in {".swift", ".m", ".h", ".kt", ".py"}:
                files.append(str(path.relative_to(self.project_path)))
        return sorted(files)

    def _read_codebase_notes(self) -> str:
        """Read CODEBASE.md or similar context file from the project if it exists."""
        for name in ["CODEBASE.md", "ARCHITECTURE.md", "README.md"]:
            p = self.project_path / name
            if p.exists():
                try:
                    return p.read_text(encoding="utf-8")[:8000]  # first 8000 chars
                except Exception:
                    pass
        return ""

    # ------------------------------------------------------------------ #
    #  Artifact persistence                                               #
    # ------------------------------------------------------------------ #

    def _save_artifact(self, filename: str, data: dict) -> None:
        artifacts_dir = self.project_path / ".agents_team"
        artifacts_dir.mkdir(exist_ok=True)
        path = artifacts_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------ #
    #  Display helpers                                                    #
    # ------------------------------------------------------------------ #

    def _print_phase(self, phase: Phase, context: str = "") -> None:
        self.reporter.phase(phase.value, context)

    def _print_sprint_summary(self, result: SprintResult) -> None:
        summary = {
            "sprint": result.sprint_number,
            "completed": len(result.completed),
            "flagged": len(result.flagged),
            "files_written": len(result.all_files_written),
            "flagged_details": [
                {"story_id": r.story_id, "reason": r.flag_reason}
                for r in result.flagged
            ],
        }
        self.reporter.summary(summary)
        # Also print to terminal
        print(f"\n{'═' * 60}")
        print(f"  SPRINT {result.sprint_number} SUMMARY")
        print(f"{'═' * 60}")
        print(f"  ✅ Completed : {len(result.completed)} stories")
        print(f"  🚩 Flagged   : {len(result.flagged)} stories")
        for r in result.flagged:
            print(f"     • {r.story_id}: {r.flag_reason}")
        print(f"  📁 Files written: {len(result.all_files_written)}")
        print(f"{'═' * 60}\n")
