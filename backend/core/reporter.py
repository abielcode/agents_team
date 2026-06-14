"""
reporter.py — Pipeline streaming reporter.

Replaces bare print() calls with typed messages that go to:
  1. stdout (terminal / CLI)
  2. WebSocket broadcasts (when a sprint_id is set)

Message types (match frontend StreamingOutput.jsx):
  { type: "phase",   phase: str, story_id: str | null }
  { type: "token",   agent: str, delta: str }
  { type: "status",  story_id: str, status: "done"|"flagged", retry_count: int }
  { type: "cost",    agent: str, tokens_in: int, tokens_out: int, cost_usd: float }
  { type: "log",     level: "info"|"warn"|"error", message: str }
  { type: "summary", data: dict }
"""

from __future__ import annotations

import asyncio
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..api.main import ConnectionManager


class Reporter:
    """
    Thin wrapper that prints to stdout AND broadcasts to WebSocket clients.
    Pass sprint_id + manager to enable WebSocket streaming.
    Set sprint_id=None for CLI-only mode (plain print).
    """

    def __init__(
        self,
        sprint_id: Optional[int] = None,
        manager: Optional["ConnectionManager"] = None,
    ):
        self.sprint_id = sprint_id
        self.manager = manager

    # ── Typed message senders ─────────────────────────────────────────────

    def phase(self, phase: str, context: str = "") -> None:
        label = f"[{context}]" if context else ""
        self._print(f"\n{'─' * 60}\n  PHASE: {phase}{label}\n{'─' * 60}")
        self._broadcast({"type": "phase", "phase": phase, "context": context})

    def token(self, agent: str, delta: str) -> None:
        print(delta, end="", flush=True)
        self._broadcast({"type": "token", "agent": agent, "delta": delta})

    def story_status(self, story_id: str, status: str, retry_count: int = 0, reason: str = "") -> None:
        icon = "✅" if status == "done" else "🚩"
        self._print(f"\n  {icon} {story_id} — {status}" + (f": {reason}" if reason else ""))
        self._broadcast({
            "type": "status",
            "story_id": story_id,
            "status": status,
            "retry_count": retry_count,
            "reason": reason,
        })

    def cost(self, agent: str, tokens_in: int, tokens_out: int, cost_usd: float, provider: str) -> None:
        cost_str = f"${cost_usd:.6f}" if cost_usd > 0 else "free (ollama)"
        self._print(f"  💰 {agent}: {tokens_in}in/{tokens_out}out — {cost_str}")
        self._broadcast({
            "type": "cost",
            "agent": agent,
            "provider": provider,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost_usd,
        })

    def log(self, message: str, level: str = "info") -> None:
        prefix = {"info": "[INFO]", "warn": "[WARN]", "error": "[ERROR]"}.get(level, "[INFO]")
        self._print(f"  {prefix} {message}")
        self._broadcast({"type": "log", "level": level, "message": message})

    def summary(self, data: dict) -> None:
        self._broadcast({"type": "summary", "data": data})

    def agent_thinking(self, agent: str) -> None:
        self._print(f"\n{'─' * 60}\n  [{agent.upper()}] thinking...\n{'─' * 60}")
        self._broadcast({"type": "log", "level": "info", "message": f"{agent} thinking..."})

    def newline(self) -> None:
        print()

    # ── Internal ──────────────────────────────────────────────────────────

    def _print(self, msg: str) -> None:
        print(msg)

    def _broadcast(self, message: dict) -> None:
        if self.sprint_id is None or self.manager is None:
            return
        # Schedule the coroutine on the running event loop (fire-and-forget)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    self.manager.broadcast(self.sprint_id, message)
                )
        except Exception:
            pass  # Never let broadcast failure crash the pipeline


# Singleton CLI reporter (no WebSocket)
CLI_REPORTER = Reporter()
