"""
cost_tracker.py — Token counting, USD cost calculation, cost guard enforcement.
Tracks per-agent, per-story, and per-sprint totals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .gateway import GatewayResponse


WARN_COLOR = "\033[93m"
STOP_COLOR = "\033[91m"
RESET = "\033[0m"


@dataclass
class AgentRunCost:
    agent_name: str
    provider: str
    model: str
    story_id: Optional[str]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class SprintCostSummary:
    sprint_number: int
    runs: list[AgentRunCost] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.runs)

    @property
    def claude_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.runs if r.provider == "anthropic")

    @property
    def claude_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.runs if r.provider == "anthropic")

    @property
    def claude_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.runs if r.provider == "anthropic")

    def by_agent(self) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for run in self.runs:
            if run.agent_name not in result:
                result[run.agent_name] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                    "provider": run.provider,
                    "model": run.model,
                }
            result[run.agent_name]["calls"] += 1
            result[run.agent_name]["input_tokens"] += run.input_tokens
            result[run.agent_name]["output_tokens"] += run.output_tokens
            result[run.agent_name]["cost_usd"] += run.cost_usd
        return result

    def to_dict(self) -> dict:
        return {
            "sprint": self.sprint_number,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "claude_cost_usd": round(self.claude_cost_usd, 6),
            "claude_tokens": {
                "input": self.claude_input_tokens,
                "output": self.claude_output_tokens,
            },
            "by_agent": self.by_agent(),
            "run_count": len(self.runs),
        }


class CostGuardError(Exception):
    """Raised when the hard-stop cost limit is exceeded."""


class CostTracker:
    """
    Tracks token usage and USD cost across all agent runs in a sprint.
    Enforces warn/hard-stop thresholds from team_config cost_guard section.
    """

    ANTHROPIC_PRICING: dict[str, dict] = {
        "claude-haiku-4-5-20251001": {
            "input_per_1m": 0.80,
            "output_per_1m": 4.00,
            "cache_write_per_1m": 1.00,
            "cache_read_per_1m": 0.08,
        }
    }

    def __init__(self, config: dict, sprint_number: int = 1):
        self.config = config
        self.cost_guard = config["cost_guard"]
        self.sprint = SprintCostSummary(sprint_number=sprint_number)
        self._warned = False

    def record(
        self,
        agent_name: str,
        response: GatewayResponse,
        story_id: Optional[str] = None,
    ) -> AgentRunCost:
        cost = self._calculate_cost(response)
        run = AgentRunCost(
            agent_name=agent_name,
            provider=response.provider,
            model=response.model,
            story_id=story_id,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_read_tokens=response.cache_read_tokens,
            cache_write_tokens=response.cache_write_tokens,
            cost_usd=cost,
        )
        self.sprint.runs.append(run)
        self._enforce_guards()
        return run

    def _calculate_cost(self, response: GatewayResponse) -> float:
        if response.provider == "ollama":
            return 0.0
        pricing = self.ANTHROPIC_PRICING.get(response.model) or (
            self.config["providers"]["anthropic"]["pricing"].get(response.model, {})
        )
        if not pricing:
            return 0.0
        return round(
            response.input_tokens * pricing["input_per_1m"] / 1_000_000
            + response.output_tokens * pricing["output_per_1m"] / 1_000_000
            + response.cache_write_tokens * pricing.get("cache_write_per_1m", 0) / 1_000_000
            + response.cache_read_tokens * pricing.get("cache_read_per_1m", 0) / 1_000_000,
            8,
        )

    def _enforce_guards(self) -> None:
        claude_usd = self.sprint.claude_cost_usd
        warn = self.cost_guard["warn_usd_per_sprint"]
        stop = self.cost_guard["hard_stop_usd_per_sprint"]

        if claude_usd >= stop:
            msg = (
                f"{STOP_COLOR}[COST GUARD] HARD STOP: Claude spend "
                f"${claude_usd:.4f} exceeds limit ${stop:.2f}/sprint{RESET}"
            )
            print(msg)
            raise CostGuardError(msg)

        if claude_usd >= warn and not self._warned:
            self._warned = True
            print(
                f"{WARN_COLOR}[COST GUARD] WARNING: Claude spend "
                f"${claude_usd:.4f} approaching limit ${stop:.2f}{RESET}"
            )

    def check_claude_tokens(self, estimated_input: int) -> None:
        """Pre-flight check before calling Anthropic."""
        max_tokens = self.cost_guard["max_claude_tokens_per_sprint"]
        current = self.sprint.claude_input_tokens + self.sprint.claude_output_tokens
        if current + estimated_input > max_tokens:
            raise CostGuardError(
                f"Claude token limit ({max_tokens}) would be exceeded. "
                f"Current: {current}, requested: {estimated_input}"
            )

    def print_summary(self) -> None:
        s = self.sprint.to_dict()
        print("\n" + "=" * 60)
        print(f"  SPRINT {s['sprint']} COST SUMMARY")
        print("=" * 60)
        print(f"  Total cost:  ${s['total_cost_usd']:.4f}")
        print(f"  Claude cost: ${s['claude_cost_usd']:.4f}")
        print(f"  Claude tokens: {s['claude_tokens']['input']} in / {s['claude_tokens']['output']} out")
        print("\n  By agent:")
        for name, data in s["by_agent"].items():
            cost_str = f"${data['cost_usd']:.4f}" if data["cost_usd"] > 0 else "free (ollama)"
            print(
                f"    {name:<15} {data['calls']:>2} calls  "
                f"{data['input_tokens']:>6} in / {data['output_tokens']:>6} out  "
                f"{cost_str}"
            )
        print("=" * 60 + "\n")

    def to_dict(self) -> dict:
        return self.sprint.to_dict()
