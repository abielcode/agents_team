"""
git_guard.py — Git safety checker.

Before the pipeline writes any files:
1. Detect if the project is a git repo.
2. Get list of uncommitted (dirty) files.
3. Compare against files the pipeline intends to write.
4. Warn on overlap — block if --git-safe is set.

Also provides helpers for:
- Checking if a path is git-ignored (so scanner can skip it)
- Reading current branch name
"""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List


@dataclass
class GitStatus:
    is_git_repo: bool
    branch: str = ""
    dirty_files: list[str] = field(default_factory=list)   # relative paths with uncommitted changes
    untracked_files: list[str] = field(default_factory=list)
    ahead: int = 0      # commits ahead of remote
    has_remote: bool = False


class GitGuardError(Exception):
    """Raised when --git-safe is set and there are conflicting dirty files."""


WARN_COLOR  = "\033[93m"
ERROR_COLOR = "\033[91m"
RESET       = "\033[0m"
INFO_COLOR  = "\033[94m"


class GitGuard:
    """
    Checks git state of a project before the pipeline runs.
    Run check() before any file writes.
    """

    def __init__(self, project_path: str, safe_mode: bool = False):
        self.project_path = Path(project_path).resolve()
        self.safe_mode = safe_mode  # if True, raise on overlap instead of warn
        self._status: Optional[GitStatus] = None

    # ── Public API ────────────────────────────────────────────────────────

    def check(self, planned_writes: Optional[List[str]] = None) -> GitStatus:
        """
        Run git status. Warn (or raise) on overlap with planned_writes.
        Returns GitStatus. Call this before any pipeline file writes.
        """
        status = self._get_status()
        self._status = status

        if not status.is_git_repo:
            print(f"{INFO_COLOR}[GIT] Project is not a git repository — skipping git checks{RESET}")
            return status

        print(f"{INFO_COLOR}[GIT] Branch: {status.branch}{RESET}")

        if not status.dirty_files and not status.untracked_files:
            print(f"{INFO_COLOR}[GIT] Working tree is clean ✓{RESET}")
            return status

        print(f"{WARN_COLOR}[GIT] Dirty files ({len(status.dirty_files)} modified, "
              f"{len(status.untracked_files)} untracked):{RESET}")
        for f in status.dirty_files[:10]:
            print(f"  ~ {f}")
        if len(status.dirty_files) > 10:
            print(f"  ... and {len(status.dirty_files) - 10} more")

        if planned_writes:
            overlap = self._find_overlap(status.dirty_files, planned_writes)
            if overlap:
                msg = (
                    f"[GIT] Pipeline intends to modify {len(overlap)} file(s) "
                    f"that have uncommitted changes:\n"
                    + "\n".join(f"  ⚠ {f}" for f in overlap)
                )
                if self.safe_mode:
                    raise GitGuardError(
                        f"{ERROR_COLOR}{msg}\n"
                        f"Run 'git stash' or commit your changes before running the pipeline.{RESET}"
                    )
                else:
                    print(f"{WARN_COLOR}{msg}")
                    print(f"  Tip: run with --git-safe to block on overlap, or 'git stash' first.{RESET}")
            else:
                print(f"{INFO_COLOR}[GIT] No overlap with planned writes ✓{RESET}")

        return status

    def is_ignored(self, path: str) -> bool:
        """Return True if the path is git-ignored (for scanner to skip)."""
        if not self._is_git_repo():
            return False
        try:
            result = subprocess.run(
                ["git", "check-ignore", "-q", path],
                cwd=str(self.project_path),
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def current_branch(self) -> str:
        status = self._get_status()
        return status.branch

    def dirty_files(self) -> list[str]:
        status = self._get_status()
        return status.dirty_files

    def print_summary(self) -> None:
        if not self._status:
            return
        s = self._status
        if not s.is_git_repo:
            return
        print(f"\n[GIT] Branch: {s.branch} | "
              f"Modified: {len(s.dirty_files)} | "
              f"Untracked: {len(s.untracked_files)}")

    # ── Internal ──────────────────────────────────────────────────────────

    def _is_git_repo(self) -> bool:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(self.project_path),
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _get_status(self) -> GitStatus:
        if self._status is not None:
            return self._status

        if not self._is_git_repo():
            return GitStatus(is_git_repo=False)

        # Branch name
        branch = ""
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.project_path),
                capture_output=True, text=True,
            )
            branch = r.stdout.strip()
        except Exception:
            pass

        # Dirty + untracked files
        dirty, untracked = [], []
        try:
            r = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.project_path),
                capture_output=True, text=True,
            )
            for line in r.stdout.splitlines():
                if not line.strip():
                    continue
                status_code = line[:2].strip()
                filepath = line[3:].strip()
                # Handle renames: "old -> new"
                if " -> " in filepath:
                    filepath = filepath.split(" -> ")[-1]
                if status_code == "??":
                    untracked.append(filepath)
                else:
                    dirty.append(filepath)
        except Exception:
            pass

        # Commits ahead of remote
        ahead = 0
        has_remote = False
        try:
            r = subprocess.run(
                ["git", "rev-list", "--count", "@{u}..HEAD"],
                cwd=str(self.project_path),
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                ahead = int(r.stdout.strip() or 0)
                has_remote = True
        except Exception:
            pass

        return GitStatus(
            is_git_repo=True,
            branch=branch,
            dirty_files=dirty,
            untracked_files=untracked,
            ahead=ahead,
            has_remote=has_remote,
        )

    def _find_overlap(self, dirty: list[str], planned: list[str]) -> list[str]:
        """Find files that are both dirty and planned to be written."""
        dirty_set = {Path(f).as_posix() for f in dirty}
        overlap = []
        for p in planned:
            if Path(p).as_posix() in dirty_set:
                overlap.append(p)
        return overlap
