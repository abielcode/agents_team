"""
gateway.py — Provider abstraction layer.
Routes calls to Anthropic or Ollama (openai-compatible).
Supports streaming and non-streaming responses.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import anthropic
from openai import AsyncOpenAI


@dataclass
class GatewayResponse:
    content: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    model: str = ""
    provider: str = ""


@dataclass
class StreamChunk:
    delta: str
    done: bool = False
    final: Optional[GatewayResponse] = None


class Gateway:
    """
    Single abstraction over Anthropic and Ollama providers.
    All agents call gateway.complete() or gateway.stream().
    """

    def __init__(self, config: dict):
        self.config = config
        self._anthropic: Optional[anthropic.AsyncAnthropic] = None
        self._ollama: Optional[AsyncOpenAI] = None

    def _get_anthropic(self) -> anthropic.AsyncAnthropic:
        if self._anthropic is None:
            api_key = os.environ.get(
                self.config["providers"]["anthropic"]["api_key_env"]
            )
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
            self._anthropic = anthropic.AsyncAnthropic(api_key=api_key)
        return self._anthropic

    def _get_ollama(self) -> AsyncOpenAI:
        if self._ollama is None:
            ollama_cfg = self.config["providers"]["ollama"]
            self._ollama = AsyncOpenAI(
                base_url=ollama_cfg["base_url"],
                api_key=ollama_cfg["api_key"],
            )
        return self._ollama

    # ------------------------------------------------------------------ #
    #  Non-streaming completion                                           #
    # ------------------------------------------------------------------ #

    async def complete(
        self,
        agent_name: str,
        messages: list[dict],
        system_prompt: str,
        use_cache: bool = False,
    ) -> GatewayResponse:
        agent_cfg = self.config["agents"][agent_name]
        provider = agent_cfg["provider"]
        model = agent_cfg["model"]
        max_tokens = agent_cfg["max_tokens"]

        if provider == "anthropic":
            return await self._complete_anthropic(
                model, max_tokens, messages, system_prompt, use_cache
            )
        elif provider == "ollama":
            force_json = agent_cfg.get("output_format", "json") == "json"
            return await self._complete_ollama(
                model, max_tokens, messages, system_prompt, force_json=force_json
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _complete_anthropic(
        self,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system_prompt: str,
        use_cache: bool,
    ) -> GatewayResponse:
        client = self._get_anthropic()

        if use_cache:
            system: list[dict] | str = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system = system_prompt

        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )

        usage = response.usage
        return GatewayResponse(
            content=response.content[0].text,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
            model=model,
            provider="anthropic",
        )

    async def _complete_ollama(
        self,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system_prompt: str,
        force_json: bool = True,
    ) -> GatewayResponse:
        client = self._get_ollama()
        all_messages = [{"role": "system", "content": system_prompt}] + messages

        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            messages=all_messages,
        )
        if force_json:
            kwargs["extra_body"] = {"format": "json"}

        response = await client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        usage = response.usage

        return GatewayResponse(
            content=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=model,
            provider="ollama",
        )

    # ------------------------------------------------------------------ #
    #  Streaming completion                                               #
    # ------------------------------------------------------------------ #

    async def stream(
        self,
        agent_name: str,
        messages: list[dict],
        system_prompt: str,
        use_cache: bool = False,
    ) -> AsyncIterator[StreamChunk]:
        agent_cfg = self.config["agents"][agent_name]
        provider = agent_cfg["provider"]
        model = agent_cfg["model"]
        max_tokens = agent_cfg["max_tokens"]

        force_json = agent_cfg.get("output_format", "json") == "json"

        if provider == "anthropic":
            async for chunk in self._stream_anthropic(
                model, max_tokens, messages, system_prompt, use_cache
            ):
                yield chunk
        elif provider == "ollama":
            async for chunk in self._stream_ollama(
                model, max_tokens, messages, system_prompt, force_json=force_json
            ):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _stream_anthropic(
        self,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system_prompt: str,
        use_cache: bool,
    ) -> AsyncIterator[StreamChunk]:
        client = self._get_anthropic()

        if use_cache:
            system: list[dict] | str = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system = system_prompt

        full_text = ""
        input_tokens = 0
        output_tokens = 0
        cache_read = 0
        cache_write = 0

        async with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_text += text
                yield StreamChunk(delta=text)

            final_msg = await stream.get_final_message()
            usage = final_msg.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            cache_read = getattr(usage, "cache_read_input_tokens", 0)
            cache_write = getattr(usage, "cache_creation_input_tokens", 0)

        yield StreamChunk(
            delta="",
            done=True,
            final=GatewayResponse(
                content=full_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
                model=model,
                provider="anthropic",
            ),
        )

    async def _stream_ollama(
        self,
        model: str,
        max_tokens: int,
        messages: list[dict],
        system_prompt: str,
        force_json: bool = True,
    ) -> AsyncIterator[StreamChunk]:
        client = self._get_ollama()
        all_messages = [{"role": "system", "content": system_prompt}] + messages
        full_text = ""
        input_tokens = 0
        output_tokens = 0

        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            messages=all_messages,
            stream=True,
        )
        if force_json:
            kwargs["extra_body"] = {"format": "json"}

        stream = await client.chat.completions.create(**kwargs)

        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            full_text += delta
            if delta:
                yield StreamChunk(delta=delta)
            if chunk.usage:
                input_tokens = chunk.usage.prompt_tokens
                output_tokens = chunk.usage.completion_tokens

        yield StreamChunk(
            delta="",
            done=True,
            final=GatewayResponse(
                content=full_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=model,
                provider="ollama",
            ),
        )

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def extract_json(text: str) -> dict:
        """
        Extract JSON from agent output robustly:
        1. Strip markdown code fences
        2. Find the outermost { ... } block
        3. Use json.loads — if that fails, try to find a valid JSON substring
        """
        import re

        text = text.strip()

        # Strip markdown fences: ```json ... ``` or ``` ... ```
        if text.startswith("```"):
            lines = text.split("\n")
            end = -1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[1:end]).strip()

        # Fast path — try parsing as-is
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find the first { and last } to extract outermost JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        # Last resort: scan for any valid JSON object in the text
        for match in re.finditer(r'\{', text):
            s = match.start()
            # Try progressively larger substrings from this opening brace
            for e in range(len(text) - 1, s, -1):
                if text[e] == '}':
                    try:
                        return json.loads(text[s:e + 1])
                    except json.JSONDecodeError:
                        continue
                    break

        raise ValueError(f"No valid JSON found in agent output. Raw output (first 500 chars):\n{text[:500]}")
