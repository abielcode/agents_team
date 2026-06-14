"""
models.py — SQLAlchemy ORM models.
Matches the data model in PRD v2.0 section 5.
Uses SQLite (dev). Async-compatible via aiosqlite.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


# ─────────────────────────────────────────────
#  Base
# ─────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
#  JSON helpers
# ─────────────────────────────────────────────

def _json_get(value: Optional[str]):
    if value is None:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _json_set(value) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value)


# ─────────────────────────────────────────────
#  Models
# ─────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)
    project_path = Column(String(1024), nullable=False)
    context = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    prds = relationship("PRD", back_populates="project", cascade="all, delete-orphan")
    sprints = relationship("Sprint", back_populates="project", cascade="all, delete-orphan")
    team_config = relationship("TeamConfig", back_populates="project", uselist=False, cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "platform": self.platform,
            "project_path": self.project_path,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PRD(Base):
    __tablename__ = "prds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    raw_input = Column(Text, nullable=True)
    structured_prd = Column(Text, nullable=True)        # JSON
    status = Column(String(50), default="draft")        # draft | approved

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="prds")
    epics = relationship("Epic", back_populates="prd", cascade="all, delete-orphan")

    @property
    def structured_prd_dict(self):
        return _json_get(self.structured_prd)

    @structured_prd_dict.setter
    def structured_prd_dict(self, value) -> None:
        self.structured_prd = _json_set(value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "raw_input": self.raw_input,
            "structured_prd": self.structured_prd_dict,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Epic(Base):
    __tablename__ = "epics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prd_id = Column(Integer, ForeignKey("prds.id"), nullable=False)
    epic_ref = Column(String(50), nullable=True)        # "epic_001"
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=0)
    status = Column(String(50), default="backlog")      # backlog | in_sprint | done | blocked

    prd = relationship("PRD", back_populates="epics")
    stories = relationship("UserStory", back_populates="epic", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prd_id": self.prd_id,
            "epic_ref": self.epic_ref,
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "stories": [s.to_dict() for s in self.stories],
        }


class UserStory(Base):
    __tablename__ = "user_stories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    epic_id = Column(Integer, ForeignKey("epics.id"), nullable=False)
    story_ref = Column(String(50), nullable=True)       # "US001"
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    acceptance_criteria = Column(Text, nullable=True)   # JSON list
    story_points = Column(Integer, default=3)
    status = Column(String(50), default="backlog")      # backlog | in_sprint | done | blocked | flagged
    sprint_id = Column(Integer, ForeignKey("sprints.id"), nullable=True)
    depends_on = Column(Text, nullable=True)            # JSON list of story_refs
    platform_notes = Column(Text, nullable=True)

    epic = relationship("Epic", back_populates="stories")
    sprint = relationship("Sprint", back_populates="stories")
    agent_runs = relationship("AgentRun", back_populates="story", cascade="all, delete-orphan")

    @property
    def acceptance_criteria_list(self) -> list:
        return _json_get(self.acceptance_criteria) or []

    @acceptance_criteria_list.setter
    def acceptance_criteria_list(self, value: list) -> None:
        self.acceptance_criteria = _json_set(value)

    @property
    def depends_on_list(self) -> list:
        return _json_get(self.depends_on) or []

    @depends_on_list.setter
    def depends_on_list(self, value: list) -> None:
        self.depends_on = _json_set(value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "epic_id": self.epic_id,
            "story_ref": self.story_ref,
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria_list,
            "story_points": self.story_points,
            "status": self.status,
            "sprint_id": self.sprint_id,
            "depends_on": self.depends_on_list,
            "platform_notes": self.platform_notes,
        }


class Sprint(Base):
    __tablename__ = "sprints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    number = Column(Integer, nullable=False)
    status = Column(String(50), default="planning")     # planning | active | review | done
    plan = Column(Text, nullable=True)                  # JSON
    review = Column(Text, nullable=True)                # JSON
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="sprints")
    stories = relationship("UserStory", back_populates="sprint")
    architecture = relationship("SprintArchitecture", back_populates="sprint", uselist=False, cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="sprint", cascade="all, delete-orphan")

    @property
    def plan_dict(self):
        return _json_get(self.plan)

    @plan_dict.setter
    def plan_dict(self, value) -> None:
        self.plan = _json_set(value)

    @property
    def review_dict(self):
        return _json_get(self.review)

    @review_dict.setter
    def review_dict(self, value) -> None:
        self.review = _json_set(value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "number": self.number,
            "status": self.status,
            "plan": self.plan_dict,
            "review": self.review_dict,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class SprintArchitecture(Base):
    __tablename__ = "sprint_architectures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id"), nullable=False)
    platform = Column(String(50), nullable=False)
    document = Column(Text, nullable=True)              # JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    sprint = relationship("Sprint", back_populates="architecture")

    @property
    def document_dict(self):
        return _json_get(self.document)

    @document_dict.setter
    def document_dict(self, value) -> None:
        self.document = _json_set(value)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sprint_id": self.sprint_id,
            "platform": self.platform,
            "document": self.document_dict,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sprint_id = Column(Integer, ForeignKey("sprints.id"), nullable=False)
    story_id = Column(Integer, ForeignKey("user_stories.id"), nullable=True)
    agent_name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    input_data = Column(Text, nullable=True)            # JSON
    output_data = Column(Text, nullable=True)           # JSON
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    duration_ms = Column(Integer, default=0)
    status = Column(String(50), default="pending")      # pending | running | done | failed
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    sprint = relationship("Sprint", back_populates="agent_runs")
    story = relationship("UserStory", back_populates="agent_runs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sprint_id": self.sprint_id,
            "story_id": self.story_id,
            "agent_name": self.agent_name,
            "provider": self.provider,
            "model": self.model,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TeamConfig(Base):
    __tablename__ = "team_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, unique=True)
    agent_configs = Column(Text, nullable=True)         # JSON
    cost_guard = Column(Text, nullable=True)            # JSON
    platform_context = Column(Text, nullable=True)      # JSON

    project = relationship("Project", back_populates="team_config")

    @property
    def agent_configs_dict(self):
        return _json_get(self.agent_configs)

    @property
    def cost_guard_dict(self):
        return _json_get(self.cost_guard)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "agent_configs": self.agent_configs_dict,
            "cost_guard": self.cost_guard_dict,
        }


# ─────────────────────────────────────────────
#  DB engine + session
# ─────────────────────────────────────────────

DATABASE_URL = "sqlite+aiosqlite:///./agents_team.db"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields an async DB session."""
    async with async_session_maker() as session:
        yield session
