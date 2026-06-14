"""costs.py — Cost tracking and reporting endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ...db import AgentRun, Sprint, get_session

router = APIRouter(prefix="/projects/{project_id}/costs", tags=["costs"])


@router.get("/")
async def get_project_costs(project_id: int, db: AsyncSession = Depends(get_session)):
    """Total cost summary across all sprints for a project."""
    result = await db.execute(
        select(AgentRun).join(Sprint).where(Sprint.project_id == project_id)
    )
    runs = result.scalars().all()
    return _summarize(runs, group_by="sprint_id")


@router.get("/sprints/{sprint_id}")
async def get_sprint_costs(project_id: int, sprint_id: int, db: AsyncSession = Depends(get_session)):
    """Cost breakdown for a single sprint."""
    sprint = await db.get(Sprint, sprint_id)
    if not sprint or sprint.project_id != project_id:
        raise HTTPException(404, "Sprint not found")

    result = await db.execute(
        select(AgentRun).where(AgentRun.sprint_id == sprint_id)
    )
    runs = result.scalars().all()
    return _summarize(runs, group_by="agent_name")


def _summarize(runs: list[AgentRun], group_by: str) -> dict:
    total_cost = sum(r.cost_usd for r in runs)
    claude_cost = sum(r.cost_usd for r in runs if r.provider == "anthropic")
    claude_in = sum(r.tokens_in for r in runs if r.provider == "anthropic")
    claude_out = sum(r.tokens_out for r in runs if r.provider == "anthropic")

    groups: dict[str, dict] = {}
    for run in runs:
        key = str(getattr(run, group_by, "unknown"))
        if key not in groups:
            groups[key] = {
                "calls": 0, "tokens_in": 0, "tokens_out": 0,
                "cost_usd": 0.0, "providers": set(),
            }
        groups[key]["calls"] += 1
        groups[key]["tokens_in"] += run.tokens_in
        groups[key]["tokens_out"] += run.tokens_out
        groups[key]["cost_usd"] += run.cost_usd
        groups[key]["providers"].add(run.provider)

    # Serialize sets
    for g in groups.values():
        g["providers"] = list(g["providers"])
        g["cost_usd"] = round(g["cost_usd"], 6)

    return {
        "total_cost_usd": round(total_cost, 6),
        "claude_cost_usd": round(claude_cost, 6),
        "ollama_cost_usd": 0.0,
        "claude_tokens": {"input": claude_in, "output": claude_out},
        "total_runs": len(runs),
        f"by_{group_by}": groups,
    }
