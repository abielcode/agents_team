"""
base_agent.py — Shared agent interface.
All agents inherit from BaseAgent.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Optional

from ..core.gateway import Gateway, GatewayResponse, StreamChunk
from ..core.cost_tracker import CostTracker
from ..core.reporter import Reporter, CLI_REPORTER


class BaseAgent(ABC):
    name: str
    use_cache: bool = False

    def __init__(
        self,
        gateway: Gateway,
        cost_tracker: CostTracker,
        reporter: Optional[Reporter] = None,
    ):
        self.gateway = gateway
        self.cost_tracker = cost_tracker
        self.reporter = reporter or CLI_REPORTER

    @abstractmethod
    def system_prompt(self, platform_context: Optional[str] = None) -> str:
        """Return the system prompt, optionally injecting platform context."""

    async def run(
        self,
        messages: list[dict],
        platform_context: Optional[str] = None,
        story_id: Optional[str] = None,
        stream: bool = True,
    ) -> dict:
        """Run the agent, stream output, record cost, return parsed JSON."""
        prompt = self.system_prompt(platform_context)
        if stream:
            return await self._run_streaming(messages, prompt, story_id)
        else:
            return await self._run_blocking(messages, prompt, story_id)

    async def _run_streaming(
        self,
        messages: list[dict],
        system_prompt: str,
        story_id: Optional[str],
    ) -> dict:
        self.reporter.agent_thinking(self.name)

        full_response: Optional[GatewayResponse] = None
        buffer = ""

        async for chunk in self.gateway.stream(
            self.name, messages, system_prompt, use_cache=self.use_cache
        ):
            if chunk.done:
                full_response = chunk.final
            else:
                self.reporter.token(self.name, chunk.delta)
                buffer += chunk.delta

        self.reporter.newline()

        if full_response is None:
            full_response = GatewayResponse(
                content=buffer, input_tokens=0, output_tokens=0, model="", provider="",
            )

        run = self.cost_tracker.record(self.name, full_response, story_id)
        self.reporter.cost(
            self.name, run.input_tokens, run.output_tokens, run.cost_usd, run.provider
        )
        return self.gateway.extract_json(full_response.content)

    async def _run_blocking(
        self,
        messages: list[dict],
        system_prompt: str,
        story_id: Optional[str],
    ) -> dict:
        response = await self.gateway.complete(
            self.name, messages, system_prompt, use_cache=self.use_cache
        )
        run = self.cost_tracker.record(self.name, response, story_id)
        self.reporter.cost(
            self.name, run.input_tokens, run.output_tokens, run.cost_usd, run.provider
        )
        return self.gateway.extract_json(response.content)

    async def run_multifile(
        self,
        messages: list[dict],
        platform_context: Optional[str] = None,
        story_id: Optional[str] = None,
    ) -> dict:
        """
        Run the agent expecting delimiter-based file output instead of JSON.
        Output format expected from LLM:

        METADATA:{"story_id":"US001","notes":"..."}
        ===FILE: path/to/File.swift===
        <raw file content>
        ===END FILE===
        ===FILE: path/to/Other.swift===
        <raw file content>
        ===END FILE===

        This avoids embedding code inside JSON strings, which breaks on large files.
        """
        prompt = self.system_prompt(platform_context)
        self.reporter.agent_thinking(self.name)

        full_response: Optional[GatewayResponse] = None
        buffer = ""

        async for chunk in self.gateway.stream(
            self.name, messages, prompt, use_cache=self.use_cache
        ):
            if chunk.done:
                full_response = chunk.final
            else:
                self.reporter.token(self.name, chunk.delta)
                buffer += chunk.delta

        self.reporter.newline()

        if full_response is None:
            full_response = GatewayResponse(
                content=buffer, input_tokens=0, output_tokens=0, model="", provider="",
            )

        run = self.cost_tracker.record(self.name, full_response, story_id)
        self.reporter.cost(
            self.name, run.input_tokens, run.output_tokens, run.cost_usd, run.provider
        )
        return self._parse_multifile_output(full_response.content)

    @staticmethod
    def _parse_multifile_output(text: str) -> dict:
        """
        Parse delimiter-based multifile output into the standard files dict.
        Expected format:
            METADATA:{...json...}
            ===FILE: relative/path===
            <content>
            ===END FILE===
        """
        import re
        result = {"files": [], "notes": ""}

        # Extract metadata line
        meta_match = re.search(r"METADATA:\s*(\{.*?\})", text, re.DOTALL)
        if meta_match:
            try:
                meta = json.loads(meta_match.group(1))
                result["story_id"] = meta.get("story_id", "")
                result["notes"] = meta.get("notes", "")
            except json.JSONDecodeError:
                pass

        # Extract file blocks using delimiters
        pattern = re.compile(
            r"===FILE:\s*(.+?)===\n(.*?)===END FILE===",
            re.DOTALL
        )
        for match in pattern.finditer(text):
            path = match.group(1).strip()
            content = match.group(2)
            if content.startswith("\n"):
                content = content[1:]
            if content.endswith("\n"):
                content = content[:-1]
            result["files"].append({
                "path": path,
                "action": "create",
                "content": content,
            })

        # Fallback: if no delimiters found, try extracting from markdown code blocks
        # This handles cases where the model ignores the delimiter instructions
        if not result["files"]:
            md_pattern = re.compile(
                r"(?:```(?:swift|kotlin|python)\n)(.*?)(?:```)",
                re.DOTALL
            )
            # Also look for path hints above code blocks
            path_pattern = re.compile(
                r"(?://\s*|#\s*)?(?:File:|file:|PATH:|path:)?\s*([\w./]+\.(?:swift|kt|py))\s*\n"
            )
            for md_match in md_pattern.finditer(text):
                content = md_match.group(1).strip()
                # Try to find a path hint before this block
                before = text[:md_match.start()]
                path_match = path_pattern.findall(before)
                path = path_match[-1] if path_match else f"GeneratedFile_{len(result['files'])}.swift"
                result["files"].append({
                    "path": path,
                    "action": "create",
                    "content": content,
                })

        return result

    @staticmethod
    def user_message(content: str) -> dict:
        return {"role": "user", "content": content}

    @staticmethod
    def build_message(data: dict) -> dict:
        return {"role": "user", "content": json.dumps(data, indent=2)}
