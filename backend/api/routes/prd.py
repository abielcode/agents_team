"""prd.py — PRD creation, refinement, and approval endpoints."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...db import Project, PRD, Epic, UserStory, get_session

router = APIRouter(prefix="/projects/{project_id}/prd", tags=["prd"])


class PRDCreate(BaseModel):
    raw_input: str


class PRDUpdate(BaseModel):
    structured_prd: Optional[dict] = None


def _load_config() -> dict:
    config_path = Path(__file__).parents[2] / "config" / "team_config.json"
    with open(config_path) as f:
        return json.load(f)


@router.get("/")
async def get_prd(project_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(PRD).where(PRD.project_id == project_id).order_by(PRD.created_at.desc())
    )
    prd = result.scalars().first()
    if not prd:
        raise HTTPException(404, "No PRD found for this project")
    return prd.to_dict()


@router.post("/refine", status_code=201)
async def refine_prd(project_id: int, body: PRDCreate, db: AsyncSession = Depends(get_session)):
    """Submit raw description → Orchestrator refines into structured PRD (status=draft)."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    from ...core.gateway import Gateway
    from ...core.cost_tracker import CostTracker
    from ...agents.orchestrator import OrchestratorAgent

    config = _load_config()
    orchestrator = OrchestratorAgent(Gateway(config), CostTracker(config, 0))
    structured = await orchestrator.refine_prd(body.raw_input, project.platform)

    prd = PRD(project_id=project_id, raw_input=body.raw_input, status="draft")
    prd.structured_prd_dict = structured
    db.add(prd)
    await db.commit()
    await db.refresh(prd)
    return prd.to_dict()


@router.patch("/{prd_id}")
async def update_prd(project_id: int, prd_id: int, body: PRDUpdate, db: AsyncSession = Depends(get_session)):
    """Edit structured PRD before approving."""
    prd = await db.get(PRD, prd_id)
    if not prd or prd.project_id != project_id:
        raise HTTPException(404, "PRD not found")
    if body.structured_prd:
        prd.structured_prd_dict = body.structured_prd
    await db.commit()
    await db.refresh(prd)
    return prd.to_dict()


@router.post("/{prd_id}/approve")
async def approve_prd(project_id: int, prd_id: int, db: AsyncSession = Depends(get_session)):
    """Approve PRD → Orchestrator generates full backlog, persists epics + stories."""
    prd = await db.get(PRD, prd_id)
    if not prd or prd.project_id != project_id:
        raise HTTPException(404, "PRD not found")
    if prd.status == "approved":
        raise HTTPException(400, "PRD already approved")

    from ...core.gateway import Gateway
    from ...core.cost_tracker import CostTracker
    from ...agents.orchestrator import OrchestratorAgent

    config = _load_config()
    orchestrator = OrchestratorAgent(Gateway(config), CostTracker(config, 0))
    backlog = await orchestrator.create_backlog(prd.structured_prd_dict)

    for epic_data in backlog.get("epics", []):
        epic = Epic(
            prd_id=prd.id,
            epic_ref=epic_data.get("id"),
            name=epic_data.get("name", ""),
            description=epic_data.get("description", ""),
        )
        db.add(epic)
        await db.flush()

        for story_data in epic_data.get("stories", []):
            story = UserStory(
                epic_id=epic.id,
                story_ref=story_data.get("id"),
                title=story_data.get("title", ""),
                description=story_data.get("description", ""),
                story_points=story_data.get("story_points", 3),
                platform_notes=story_data.get("platform_notes", ""),
            )
            story.acceptance_criteria_list = story_data.get("acceptance_criteria", [])
            story.depends_on_list = story_data.get("depends_on", [])
            db.add(story)

    prd.status = "approved"
    await db.commit()
    await db.refresh(prd)
    return {"message": "PRD approved, backlog created", "prd": prd.to_dict()}
