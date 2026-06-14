"""
main.py — FastAPI application.
- REST API for all project/PRD/backlog/sprint/agent/cost operations
- WebSocket endpoint for live agent output streaming (/ws/sprint/{sprint_id})
- SQLite DB init on startup
- CORS enabled for React dev server (localhost:5173)
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ..db import init_db
from .routes import (
    projects_router,
    prd_router,
    backlog_router,
    sprints_router,
    agents_router,
    costs_router,
)


# ─────────────────────────────────────────────
#  WebSocket connection manager
# ─────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections per sprint."""

    def __init__(self):
        # sprint_id → list of WebSocket connections
        self._connections: dict[int, list[WebSocket]] = {}

    async def connect(self, sprint_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(sprint_id, []).append(ws)

    def disconnect(self, sprint_id: int, ws: WebSocket) -> None:
        if sprint_id in self._connections:
            self._connections[sprint_id].discard(ws) if hasattr(
                self._connections[sprint_id], "discard"
            ) else None
            try:
                self._connections[sprint_id].remove(ws)
            except ValueError:
                pass

    async def broadcast(self, sprint_id: int, message: dict) -> None:
        """Send a JSON message to all clients watching this sprint."""
        dead = []
        for ws in self._connections.get(sprint_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(sprint_id, ws)

    async def send(self, ws: WebSocket, message: dict) -> None:
        try:
            await ws.send_json(message)
        except Exception:
            pass


manager = ConnectionManager()


# ─────────────────────────────────────────────
#  App lifecycle
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


# ─────────────────────────────────────────────
#  App
# ─────────────────────────────────────────────

app = FastAPI(
    title="Agents Team API",
    description="AI-powered development team — backend API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(projects_router, prefix="/api/v1")
app.include_router(prd_router, prefix="/api/v1")
app.include_router(backlog_router, prefix="/api/v1")
app.include_router(sprints_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(costs_router, prefix="/api/v1")


# ─────────────────────────────────────────────
#  WebSocket — live agent streaming
# ─────────────────────────────────────────────

@app.websocket("/ws/sprint/{sprint_id}")
async def sprint_websocket(sprint_id: int, ws: WebSocket):
    """
    WebSocket endpoint for live sprint execution streaming.

    Message types sent to client:
      { "type": "phase",   "phase": "CODING",  "story_id": "US001" }
      { "type": "token",   "agent": "coder",   "delta": "..." }
      { "type": "status",  "story_id": "US001", "status": "done"|"flagged" }
      { "type": "cost",    "agent": "coder",   "cost_usd": 0.0, "tokens_in": 100 }
      { "type": "summary", "data": { ...sprint summary... } }
      { "type": "error",   "message": "..." }
      { "type": "ping" }   (heartbeat every 30s)
    """
    await manager.connect(sprint_id, ws)
    try:
        # Heartbeat loop — keep connection alive during long runs
        while True:
            try:
                # Wait for client message (ping/pong or disconnect)
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                msg = json.loads(data) if data else {}
                if msg.get("type") == "ping":
                    await manager.send(ws, {"type": "pong"})
            except asyncio.TimeoutError:
                # Send server-side ping
                await manager.send(ws, {"type": "ping"})
            except WebSocketDisconnect:
                break
    finally:
        manager.disconnect(sprint_id, ws)


# ─────────────────────────────────────────────
#  Health check
# ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/")
async def root():
    return {
        "name": "Agents Team API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# ─────────────────────────────────────────────
#  Dev entrypoint
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8000, reload=True)
