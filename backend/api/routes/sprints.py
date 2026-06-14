"""
sprints.py — Sprint planning, execution, and review endpoints.
The /run endpoint triggers the full pipeline and streams progress via WebSocket.
"""

from __future__ import annotations
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...db import Project, Sprint, SprintArchitecture, UserStory, PRD, Epic, get_session, async_session_maker

router = APIRouter(prefix="/projects/{project_id}/sprints", tags=["sprints"])


def _load_config() -> dict:
    config_path = Path(__file__).parents[2] / "config" / "team_config.json"
    with open(config_path) as f:
        return json.load(f)


# ── Request bodies ─────────────────────────────────────────────────────────

class SprintCreate(BaseModel):
    number: int = 1
    story_refs: list[str] = []


class SprintRunOptions(BaseModel):
    dry_run: bool = False
    git_safe: bool = False
    skip_scan: bool = False
    all_anthropic: bool = False     # route all agents through Anthropic (no Ollama needed)
    task_description: str = ""      # override task description for PRD generation


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_sprints(project_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Sprint).where(Sprint.project_id == project_id).order_by(Sprint.number)
    )
    return [s.to_dict() for s in result.scalars().all()]


@router.get("/{sprint_id}")
async def get_sprint(project_id: int, sprint_id: int, db: AsyncSession = Depends(get_session)):
    sprint = await db.get(Sprint, sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(404, "Sprint not found")
    return sprint.to_dict()


@router.post("/", status_code=201)
async def create_sprint(
    project_id: int,
    body: SprintCreate,
    db: AsyncSession = Depends(get_session),
):
    """Create a sprint record (status=planning). Call /run to execute it."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    sprint = Sprint(project_id=project_id, number=body.number, status="planning")
    if body.story_refs:
        sprint.plan_dict = {"sprint": body.number, "stories": body.story_refs}
    db.add(sprint)
    await db.flush()  # get sprint.id before linking stories

    if body.story_refs:
        result = await db.execute(
            select(UserStory).where(UserStory.story_ref.in_(body.story_refs))
        )
        for story in result.scalars().all():
            story.sprint_id = sprint.id
            story.status = "in_sprint"

    await db.commit()
    await db.refresh(sprint)
    return sprint.to_dict()


@router.post("/{sprint_id}/run")
async def run_sprint(
    project_id: int,
    sprint_id: int,
    body: SprintRunOptions,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """
    Trigger full pipeline execution for a sprint.
    Runs in background — connect to WebSocket /ws/sprint/{sprint_id} for live output.
    """
    sprint = await db.get(Sprint, sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(404, "Sprint not found")
    if sprint.status == "active":
        raise HTTPException(400, "Sprint already running")
    if sprint.status == "done":
        raise HTTPException(400, "Sprint already completed")

    project = await db.get(Project, project_id)

    sprint.status = "active"
    sprint.started_at = datetime.utcnow()
    await db.commit()

    background_tasks.add_task(_execute_sprint, project, sprint, body)
    return {
        "message": f"Sprint {sprint.number} started",
        "sprint_id": sprint_id,
        "ws_url": f"/ws/sprint/{sprint_id}",
        "options": body.model_dump(),
    }


async def _execute_sprint(project, sprint, options: SprintRunOptions):
    """Background task: runs the full pipeline and persists results."""
    from ...core.pipeline import Pipeline
    from ...core.reporter import Reporter
    from ...api.main import manager   # WebSocket connection manager

    config = _load_config()

    # Apply all-anthropic override
    if options.all_anthropic:
        for agent in config["agents"].values():
            agent["provider"] = "anthropic"
            agent["model"] = "claude-haiku-4-5-20251001"
        config["cost_guard"]["warn_usd_per_sprint"] = 0.50
        config["cost_guard"]["hard_stop_usd_per_sprint"] = 2.00

    # Create a WebSocket-aware reporter
    reporter = Reporter(sprint_id=sprint.id, manager=manager)

    async with async_session_maker() as db:
        try:
            # Load PRD and backlog from DB so the pipeline doesn't regenerate them
            prd_result = await db.execute(
                select(PRD).where(PRD.project_id == project.id).order_by(PRD.created_at.desc())
            )
            prd_obj = prd_result.scalars().first()
            prd_dict = prd_obj.structured_prd_dict if prd_obj else None

            epic_result = await db.execute(
                select(Epic)
                .join(PRD)
                .where(PRD.project_id == project.id)
                .options(selectinload(Epic.stories))
            )
            epics = epic_result.scalars().all()
            # Remap story "id" to story_ref so pipeline can look them up by ref (e.g. "US001")
            def epic_to_pipeline_dict(epic):
                d = epic.to_dict()
                for s in d.get("stories", []):
                    s["id"] = s.get("story_ref", s["id"])
                return d
            backlog_dict = {"epics": [epic_to_pipeline_dict(e) for e in epics]} if epics else None

            pipeline = Pipeline(
                config=config,
                project_path=project.project_path,
                platform_name=project.platform,
                sprint_number=sprint.number,
                dry_run=options.dry_run,
                git_safe=options.git_safe,
                skip_scan=options.skip_scan,
                reporter=reporter,
            )

            result = await pipeline.run_sprint(
                task_description=options.task_description,
                prd=prd_dict,
                backlog=backlog_dict,
                sprint_plan=sprint.plan_dict,
            )

            # Persist architecture
            if result.architecture:
                arch = SprintArchitecture(sprint_id=sprint.id, platform=project.platform)
                arch.document_dict = result.architecture
                db.add(arch)

            # Update story statuses
            for story_result in result.story_results:
                res = await db.execute(
                    select(UserStory).where(UserStory.story_ref == story_result.story_id)
                )
                story = res.scalars().first()
                if story:
                    story.status = "done" if story_result.status == "done" else "flagged"

            # Persist sprint review
            sprint_obj = await db.get(Sprint, sprint.id)
            sprint_obj.status = "done"
            sprint_obj.completed_at = datetime.utcnow()
            sprint_obj.review_dict = result.review or {
                "sprint": sprint.number,
                "summary": "Sprint completed.",
                "completed": [],
                "flagged": [],
                "files_created": [],
                "files_modified": [],
                "cost": result.cost or {},
                "next_sprint_proposal": None,
            }

            await db.commit()

            # Send final summary over WebSocket
            if result.cost:
                await manager.broadcast(sprint.id, {"type": "summary", "data": result.cost})

        except Exception as e:
            reporter.log(f"Pipeline error: {e}", level="error")
            sprint_obj = await db.get(Sprint, sprint.id)
            if sprint_obj:
                sprint_obj.status = "planning"  # reset so it can be retried
                await db.commit()


# ── Status & review ────────────────────────────────────────────────────────

@router.get("/{sprint_id}/status")
async def sprint_status(project_id: int, sprint_id: int, db: AsyncSession = Depends(get_session)):
    sprint = await db.get(Sprint, sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(404, "Sprint not found")

    result = await db.execute(select(UserStory).where(UserStory.sprint_id == sprint_id))
    stories = result.scalars().all()

    return {
        "sprint_id": sprint_id,
        "number": sprint.number,
        "status": sprint.status,
        "started_at": sprint.started_at.isoformat() if sprint.started_at else None,
        "completed_at": sprint.completed_at.isoformat() if sprint.completed_at else None,
        "stories": {
            "total": len(stories),
            "done": sum(1 for s in stories if s.status == "done"),
            "flagged": sum(1 for s in stories if s.status == "flagged"),
            "in_progress": sum(1 for s in stories if s.status == "in_sprint"),
        },
        "review": sprint.review_dict,
    }


@router.post("/{sprint_id}/reset")
async def reset_sprint(
    project_id: int,
    sprint_id: int,
    db: AsyncSession = Depends(get_session),
):
    """Reset a sprint back to planning status so it can be re-run."""
    sprint = await db.get(Sprint, sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(404, "Sprint not found")

    sprint.status = "planning"
    sprint.started_at = None
    sprint.completed_at = None
    sprint.review_dict = None

    # Re-assign stories from plan_dict by story_ref
    story_refs = (sprint.plan_dict or {}).get("stories", [])
    if story_refs:
        result = await db.execute(
            select(UserStory).where(UserStory.story_ref.in_(story_refs))
        )
        for story in result.scalars().all():
            story.sprint_id = sprint_id
            story.status = "in_sprint"

    await db.commit()
    return {"message": f"Sprint {sprint.number} reset to planning", "sprint_id": sprint_id}


@router.post("/{sprint_id}/approve-review")
async def approve_sprint_review(
    project_id: int,
    sprint_id: int,
    db: AsyncSession = Depends(get_session),
):
    sprint = await db.get(Sprint, sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(404, "Sprint not found")
    sprint.status = "done"
    await db.commit()
    return sprint.to_dict()
