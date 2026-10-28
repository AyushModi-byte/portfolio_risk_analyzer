"""Groq adapter for the agent eval only. Nothing under backend/app imports this.

Groq serves an OpenAI-compatible chat completions API, so this uses httpx (already in
requirements-dev.txt) and adds no dependency. The deployed app keeps using Gemini.
"""

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from app.agent.llm import LLMError, LLMRateLimitError, LLMResponse, Message, ToolCall, ToolSpec

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
MAX_RATE_LIMIT_RETRIES = 3
MAX_WAIT_SECONDS = 90.0


def load_groq_key(env_file: Path) -> str:
    """GROQ_API_KEY from the environment, else from a .env file. Never printed or logged."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key or not env_file.is_file():
        return key
    for line in env_file.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() == "GROQ_API_KEY":
            return value.strip().strip("\"'")
    return ""


def _to_wire(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "assistant" and m.tool_calls:
            calls = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.args)},
                }
                for c in m.tool_calls
            ]
            out.append({"role": "assistant", "content": m.content or None, "tool_calls": calls})
        elif m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


def _parse_calls(raw_calls: list[dict[str, Any]]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for c in raw_calls:
        fn = c.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append(
            ToolCall(
                name=str(fn.get("name", "")),
                args=args if isinstance(args, dict) else {},
                id=str(c.get("id", "")),
            )
        )
    return calls


class GroqLLM:
    def __init__(self, api_key: str, model: str = DEFAULT_GROQ_MODEL, temperature: float = 0.2):
        self.model = model
        self._temperature = temperature
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"}, timeout=httpx.Timeout(60.0)
        )

    def invoke(self, messages: list[Message], tools: list[ToolSpec] | None = None) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": _to_wire(messages),
            "temperature": self._temperature,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            try:
                resp = self._client.post(GROQ_URL, json=body)
            except httpx.HTTPError as exc:
                raise LLMError(f"Model call failed ({type(exc).__name__}).") from exc
            if resp.status_code == 429:
                if attempt == MAX_RATE_LIMIT_RETRIES:
                    raise LLMRateLimitError("The AI service is rate limited; try again shortly.")
                wait = float(resp.headers.get("retry-after", "10") or 10)
                time.sleep(min(wait, MAX_WAIT_SECONDS) + 1)
                continue
            break
        if resp.status_code != 200:
            raise LLMError(f"Model call failed (HTTP {resp.status_code}).")
        try:
            msg = resp.json()["choices"][0]["message"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("Model returned an unreadable response.") from exc
        return LLMResponse(
            content=str(msg.get("content") or ""),
            tool_calls=_parse_calls(msg.get("tool_calls") or []),
            raw=msg,
        )
