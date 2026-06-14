#!/usr/bin/env python3
"""
cli.py — Agents Team CLI runner (Phase 1 + multi-project support).

Usage:
  # New project — full run from task description
  python cli.py --platform ios --task "Add a login screen" --project ~/MyApp

  # Dry-run (LLM-only verification, no real build tools)
  python cli.py --platform ios --task "Add login" --project ~/MyApp --dry-run

  # Resume an existing project by ID (reads artifacts from .agents_team/)
  python cli.py --project-id 3 --sprint 2

  # Continue from explicit artifact files
  python cli.py --platform ios --project ~/MyApp \\
    --prd .agents_team/prd.json \\
    --backlog .agents_team/backlog.json \\
    --sprint 2

  # List all known projects in the DB
  python cli.py --list-projects

Supported platforms: ios, android, django
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def load_config() -> dict:
    config_path = Path(__file__).parent / "backend" / "config" / "team_config.json"
    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(config_path) as f:
        return json.load(f)


def check_env() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "[ERROR] ANTHROPIC_API_KEY not set.\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        sys.exit(1)


def load_json_file(path: str, label: str) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        print(f"[ERROR] {label} file not found: {p}", file=sys.stderr)
        sys.exit(1)
    with open(p) as f:
        return json.load(f)


def auto_load_artifacts(artifacts_dir: Path, sprint: int) -> tuple:
    """Try to load prd, backlog, prev_arch from .agents_team/ automatically."""
    prd, backlog, prev_arch = None, None, None

    if (artifacts_dir / "prd.json").exists():
        print("[INFO] Auto-loading prd.json from project artifacts")
        prd = load_json_file(str(artifacts_dir / "prd.json"), "PRD")

    if (artifacts_dir / "backlog.json").exists():
        print("[INFO] Auto-loading backlog.json from project artifacts")
        backlog = load_json_file(str(artifacts_dir / "backlog.json"), "Backlog")

    prev_sprint = sprint - 1
    if prev_sprint >= 1:
        arch_path = artifacts_dir / f"sprint_{prev_sprint}_architecture.json"
        if arch_path.exists():
            print(f"[INFO] Auto-loading sprint {prev_sprint} architecture")
            prev_arch = load_json_file(str(arch_path), "Previous architecture")

    return prd, backlog, prev_arch


async def load_project_from_db(project_id: int) -> dict | None:
    """Load project record from SQLite DB (if API backend has been used)."""
    db_path = Path(__file__).parent / "agents_team.db"
    if not db_path.exists():
        return None
    try:
        import aiosqlite
        async with aiosqlite.connect(str(db_path)) as db:
            async with db.execute(
                "SELECT id, name, platform, project_path, context FROM projects WHERE id = ?",
                (project_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "id": row[0], "name": row[1],
                        "platform": row[2], "project_path": row[3], "context": row[4],
                    }
    except Exception as e:
        print(f"[WARN] Could not read DB: {e}")
    return None


async def list_projects_from_db() -> None:
    db_path = Path(__file__).parent / "agents_team.db"
    if not db_path.exists():
        print("No database found. Start the API server and create a project first.")
        return
    try:
        import aiosqlite
        async with aiosqlite.connect(str(db_path)) as db:
            async with db.execute(
                "SELECT id, name, platform, project_path, created_at FROM projects ORDER BY id"
            ) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            print("No projects found in DB.")
            return
        print(f"\n{'ID':<4} {'Platform':<10} {'Name':<30} {'Path'}")
        print("─" * 80)
        for row in rows:
            print(f"{row[0]:<4} {row[2]:<10} {row[1]:<30} {row[3]}")
        print()
    except Exception as e:
        print(f"[ERROR] {e}")


# ─────────────────────────────────────────────
#  Argument parser
# ─────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agents-team",
        description="AI-powered development team CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Project identification — either new or existing
    proj = parser.add_mutually_exclusive_group()
    proj.add_argument("--project", help="Path to the target project directory (new project)")
    proj.add_argument("--project-id", type=int, dest="project_id",
                      help="Resume existing project by DB ID (reads platform/path from DB)")

    parser.add_argument("--list-projects", action="store_true", dest="list_projects",
                        help="List all projects in the DB and exit")

    parser.add_argument("--platform", choices=["ios", "android", "django"],
                        help="Target platform (required for new projects)")
    parser.add_argument("--task", default=None,
                        help="Feature description (generates PRD if --prd not given)")
    parser.add_argument("--prd", default=None,
                        help="Path to existing prd.json (skips PRD refinement)")
    parser.add_argument("--backlog", default=None,
                        help="Path to existing backlog.json (skips backlog creation)")
    parser.add_argument("--sprint-plan", default=None, dest="sprint_plan",
                        help="Path to existing sprint_N_plan.json (skips sprint planning)")
    parser.add_argument("--sprint", type=int, default=1, help="Sprint number (default: 1)")
    parser.add_argument("--prev-arch", default=None, dest="prev_arch",
                        help="Path to previous sprint architecture JSON")
    parser.add_argument("--completed", default=None, nargs="*",
                        help="Story IDs already completed (space-separated)")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="LLM-only verification (no real build/lint/test tools)")
    parser.add_argument("--all-anthropic", action="store_true", dest="all_anthropic",
                        help="Route ALL agents through Anthropic (use when Ollama is not running)")
    parser.add_argument("--git-safe", action="store_true", dest="git_safe",
                        help="Block pipeline if it would overwrite files with uncommitted changes")
    parser.add_argument("--skip-scan", action="store_true", dest="skip_scan",
                        help="Skip codebase scanner even if CODEBASE.md has gaps (faster, less context)")

    return parser


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # ── List projects ─────────────────────────────────────────────────
    if args.list_projects:
        await list_projects_from_db()
        return

    # ── Resolve project ───────────────────────────────────────────────
    platform = args.platform
    project_path_str = args.project

    if args.project_id:
        project = await load_project_from_db(args.project_id)
        if not project:
            print(f"[ERROR] Project ID {args.project_id} not found in DB.", file=sys.stderr)
            sys.exit(1)
        platform = project["platform"]
        project_path_str = project["project_path"]
        print(f"[INFO] Resuming project: {project['name']} ({platform}) at {project_path_str}")

    if not platform:
        parser.error("--platform is required when not using --project-id")
    if not project_path_str:
        parser.error("--project is required when not using --project-id")
    if args.prd is None and args.task is None and not args.project_id:
        parser.error("Either --task or --prd must be provided")

    project_path = Path(project_path_str).expanduser().resolve()
    if not project_path.exists():
        print(f"[ERROR] Project path does not exist: {project_path}", file=sys.stderr)
        sys.exit(1)

    check_env()
    config = load_config()

    # ── Override all agents to Anthropic if Ollama not available ──────
    if getattr(args, 'all_anthropic', False):
        print("[INFO] --all-anthropic: routing all agents through claude-haiku")
        for agent in config["agents"].values():
            agent["provider"] = "anthropic"
            agent["model"] = "claude-haiku-4-5-20251001"
        # Raise cost guard limits for full-team Anthropic run
        config["cost_guard"]["warn_usd_per_sprint"] = 0.50
        config["cost_guard"]["hard_stop_usd_per_sprint"] = 2.00

    # ── Load artifacts ─────────────────────────────────────────────────
    prd       = load_json_file(args.prd, "PRD") if args.prd else None
    backlog   = load_json_file(args.backlog, "Backlog") if args.backlog else None
    sprint_plan = load_json_file(args.sprint_plan, "Sprint plan") if args.sprint_plan else None
    prev_arch   = load_json_file(args.prev_arch, "Prev arch") if args.prev_arch else None

    # Auto-load from .agents_team/ if not explicitly provided
    artifacts_dir = project_path / ".agents_team"
    auto_prd, auto_backlog, auto_arch = auto_load_artifacts(artifacts_dir, args.sprint)
    prd       = prd or auto_prd
    backlog   = backlog or auto_backlog
    prev_arch = prev_arch or auto_arch

    # ── Banner ─────────────────────────────────────────────────────────
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + "  AGENTS TEAM — AI Development Pipeline".center(58) + "║")
    print("╠" + "═" * 58 + "╣")
    print(f"║  Platform  : {platform:<43} ║")
    print(f"║  Project   : {str(project_path)[:43]:<43} ║")
    print(f"║  Sprint    : {args.sprint:<43} ║")
    print(f"║  Dry run   : {'yes' if args.dry_run else 'no':<43} ║")
    print(f"║  Git safe  : {'yes (blocks on dirty overlap)' if getattr(args,'git_safe',False) else 'no (warn only)':<43} ║")
    print(f"║  Scan      : {'skipped' if getattr(args,'skip_scan',False) else 'auto (fills CODEBASE.md gaps)':<43} ║")
    if getattr(args, 'all_anthropic', False):
        print(f"║  Agents    : {'all → claude-haiku (Ollama off)':<43} ║")
    if args.task:
        print(f"║  Task      : {args.task[:43]:<43} ║")
    if args.project_id:
        print(f"║  Project ID: {args.project_id:<43} ║")
    print("╚" + "═" * 58 + "╝\n")

    # ── Run pipeline ───────────────────────────────────────────────────
    sys.path.insert(0, str(Path(__file__).parent))
    from backend.core.pipeline import Pipeline

    pipeline = Pipeline(
        config=config,
        project_path=str(project_path),
        platform_name=platform,
        sprint_number=args.sprint,
        dry_run=args.dry_run,
        git_safe=getattr(args, 'git_safe', False),
        skip_scan=getattr(args, 'skip_scan', False),
    )

    result = await pipeline.run_sprint(
        task_description=args.task or "",
        prd=prd,
        backlog=backlog,
        sprint_plan=sprint_plan,
        previous_architecture=prev_arch,
        completed_story_ids=args.completed or [],
    )

    # Exit with error code if nothing completed
    if result.flagged and not result.completed:
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
