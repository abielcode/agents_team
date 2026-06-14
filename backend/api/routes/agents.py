"""agents.py — Agent team configuration endpoints."""

from __future__ import annotations
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import Project, TeamConfig, get_session

router = APIRouter(prefix="/projects/{project_id}/agents", tags=["agents"])


class AgentConfigUpdate(BaseModel):
    agent_configs: Optional[dict] = None
    cost_guard: Optional[dict] = None


@router.get("/config")
async def get_agent_config(project_id: int, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    tc = project.team_config
    if not tc:
        raise HTTPException(404, "No team config found")
    return tc.to_dict()


@router.patch("/config")
async def update_agent_config(
    project_id: int,
    body: AgentConfigUpdate,
    db: AsyncSession = Depends(get_session),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    tc = project.team_config
    if not tc:
        raise HTTPException(404, "No team config found")

    if body.agent_configs is not None:
        tc.agent_configs = json.dumps(body.agent_configs)
    if body.cost_guard is not None:
        tc.cost_guard = json.dumps(body.cost_guard)

    await db.commit()
    await db.refresh(tc)
    return tc.to_dict()


@router.get("/runs")
async def list_agent_runs(
    project_id: int,
    sprint_id: Optional[int] = None,
    agent_name: Optional[str] = None,
    db: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    from ...db import AgentRun, Sprint

    query = select(AgentRun).join(Sprint).where(Sprint.project_id == project_id)
    if sprint_id:
        query = query.where(AgentRun.sprint_id == sprint_id)
    if agent_name:
        query = query.where(AgentRun.agent_name == agent_name)
    query = query.order_by(AgentRun.created_at.desc())

    result = await db.execute(query)
    return [r.to_dict() for r in result.scalars().all()]
