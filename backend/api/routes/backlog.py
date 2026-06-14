"""backlog.py — Backlog management: epics, stories, reprioritization."""

from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...db import PRD, Epic, UserStory, get_session

router = APIRouter(prefix="/projects/{project_id}/backlog", tags=["backlog"])


class StoryUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None
    story_points: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    depends_on: Optional[List[str]] = None
    platform_notes: Optional[str] = None


class StoryCreate(BaseModel):
    epic_id: int
    story_ref: Optional[str] = None
    title: str
    description: Optional[str] = None
    acceptance_criteria: list[str] = []
    story_points: int = 3
    depends_on: list[str] = []
    platform_notes: Optional[str] = None


@router.get("/")
async def get_backlog(project_id: int, db: AsyncSession = Depends(get_session)):
    """Return full backlog: all epics + stories for the project's approved PRD."""
    result = await db.execute(
        select(PRD)
        .where(PRD.project_id == project_id, PRD.status == "approved")
        .options(selectinload(PRD.epics).selectinload(Epic.stories))
        .order_by(PRD.created_at.desc())
    )
    prd = result.scalars().first()
    if not prd:
        raise HTTPException(404, "No approved PRD found — approve a PRD first")
    return {"prd_id": prd.id, "epics": [e.to_dict() for e in prd.epics]}


@router.get("/stories/{story_id}")
async def get_story(project_id: int, story_id: int, db: AsyncSession = Depends(get_session)):
    story = await db.get(UserStory, story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    return story.to_dict()


@router.post("/stories", status_code=201)
async def create_story(project_id: int, body: StoryCreate, db: AsyncSession = Depends(get_session)):
    epic = await db.get(Epic, body.epic_id)
    if not epic:
        raise HTTPException(404, "Epic not found")

    story = UserStory(
        epic_id=body.epic_id,
        story_ref=body.story_ref,
        title=body.title,
        description=body.description,
        story_points=body.story_points,
        platform_notes=body.platform_notes,
    )
    story.acceptance_criteria_list = body.acceptance_criteria
    story.depends_on_list = body.depends_on
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story.to_dict()


@router.patch("/stories/{story_id}")
async def update_story(project_id: int, story_id: int, body: StoryUpdate, db: AsyncSession = Depends(get_session)):
    story = await db.get(UserStory, story_id)
    if not story:
        raise HTTPException(404, "Story not found")

    update = body.model_dump(exclude_none=True)
    if "acceptance_criteria" in update:
        story.acceptance_criteria_list = update.pop("acceptance_criteria")
    if "depends_on" in update:
        story.depends_on_list = update.pop("depends_on")
    for field, value in update.items():
        setattr(story, field, value)

    await db.commit()
    await db.refresh(story)
    return story.to_dict()


@router.delete("/stories/{story_id}", status_code=204)
async def delete_story(project_id: int, story_id: int, db: AsyncSession = Depends(get_session)):
    story = await db.get(UserStory, story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    await db.delete(story)
    await db.commit()
