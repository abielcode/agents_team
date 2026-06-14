"""projects.py — Project CRUD endpoints."""

from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...db import Project, TeamConfig, get_session

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    platform: str
    project_path: str
    context: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    project_path: Optional[str] = None
    context: Optional[str] = None


@router.get("/")
async def list_projects(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return [p.to_dict() for p in result.scalars().all()]


@router.post("/", status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_session)):
    if body.platform not in ("ios", "android", "django"):
        raise HTTPException(400, "platform must be ios | android | django")

    project = Project(
        name=body.name,
        platform=body.platform,
        project_path=body.project_path,
        context=body.context,
    )
    db.add(project)
    await db.flush()

    config_path = Path(__file__).parents[2] / "config" / "team_config.json"
    with open(config_path) as f:
        default_cfg = json.load(f)

    tc = TeamConfig(
        project_id=project.id,
        agent_configs=json.dumps(default_cfg["agents"]),
        cost_guard=json.dumps(default_cfg["cost_guard"]),
    )
    db.add(tc)
    await db.commit()
    await db.refresh(project)
    return project.to_dict()


@router.get("/{project_id}")
async def get_project(project_id: int, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project.to_dict()


@router.patch("/{project_id}")
async def update_project(project_id: int, body: ProjectUpdate, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project.to_dict()


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: int, db: AsyncSession = Depends(get_session)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    await db.delete(project)
    await db.commit()


@router.post("/pick-folder")
async def pick_folder():
    """
    Open a native folder picker dialog and return the selected path.
    Uses tkinter on all platforms (works on macOS, Linux, Windows).
    """
    try:
        script = (
            "import tkinter as tk; "
            "from tkinter import filedialog; "
            "root = tk.Tk(); "
            "root.withdraw(); "
            "root.call('wm', 'attributes', '.', '-topmost', True); "
            "path = filedialog.askdirectory(title='Select project folder'); "
            "print(path)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        path = result.stdout.strip()
        if not path:
            return {"path": None, "cancelled": True}
        return {"path": path, "cancelled": False}

    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Folder picker timed out")
    except Exception as e:
        raise HTTPException(500, f"Folder picker error: {e}")
