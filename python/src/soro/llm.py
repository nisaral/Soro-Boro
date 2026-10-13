"""Model access for harnesses.

Three modes, all behind one interface:

  offline  : deterministic scripted policy. No network, no GPU, fully
             reproducible. Used by the contract tests and CI.
  ollama   : local OpenAI-compatible server (the headline benchmark mode).
  openai   : any OpenAI-compatible endpoint (vLLM, SGLang, hosted APIs).

Nothing in this module decides *whether* to call a model; that is the kernel's
job. This module only answers "given these messages, what did the model say".
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

TOOL_PROTOCOL = """You are the reasoning core of an agent harness.

Reply with exactly one JSON object and nothing else:

  {"thought": "...", "tool": "<tool_name>", "args": {...}}
      call a tool

  {"thought": "...", "final": "<answer>"}
      the task is finished

Rules:
- Never invent tool names; use only the tools listed below.
- If your previous attempt failed, say so in "thought" and choose a different approach.
"""


@dataclass
class LLMReply:
    text: str
    usd: float = 0.0
    tokens: int = 0
    latency_ms: int = 0
    model: str = ""
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    final: str | None = None
    raw: str = ""


class LLMClient(Protocol):
    name: str

    def describe(self) -> str: ...

    def complete(self, messages: list[dict[str, str]], tier: str, tools: list[str]) -> LLMReply: ...


def chat_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Merge adjacent turns that share a role.

    Gemma-style chat templates reject ``user`` followed by ``user``. The
    harness records the task and the state summary as two user messages, so
    the live client folds them into one turn before the request.
    """
    merged: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role") or "user"
        if role not in {"system", "user", "assistant"}:
            role = "user"
        content = message.get("content") or ""
        if merged and merged[-1]["role"] == role:
            merged[-1]["content"] = (merged[-1]["content"] + "\n\n" + content).strip()
            continue
        merged.append({"role": role, "content": content})
    return merged


def parse_reply(text: str, model: str, usd: float, tokens: int, latency_ms: int) -> LLMReply:
    """Parse the tool protocol JSON, tolerating surrounding prose/fences."""
    payload: dict[str, Any] = {}
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```")[1] if "```" in stripped[3:] else stripped[3:]
        stripped = stripped.removeprefix("json").strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end > start:
        try:
            payload = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            payload = {}
    return LLMReply(
        text=text,
        usd=usd,
        tokens=tokens,
        latency_ms=latency_ms,
        model=model,
        tool=payload.get("tool"),
        args=payload.get("args") or {},
        final=payload.get("final"),
        raw=text,
    )


class OfflineLLM:
    """Deterministic scripted model.

    It replays a list of steps supplied by the benchmark task, which makes the
    whole runtime testable end to end without a GPU. It is explicitly *not* a
    model: it exists so the plumbing can be tested, and the pre-registration
    document says so.
    """

    name = "offline"

    def __init__(self, script: list[dict[str, Any]] | None = None, fail_at: list[int] | None = None):
        self.script = script or []
        self.fail_at = set(fail_at or [])
        self.calls = 0

    def describe(self) -> str:
        return f"offline(script={len(self.script)} steps)"

    def complete(self, messages: list[dict[str, str]], tier: str, tools: list[str]) -> LLMReply:
        idx = self.calls
        self.calls += 1
        start = time.perf_counter()
        if idx >= len(self.script):
            reply = {"thought": "script exhausted", "final": "done"}
        else:
            reply = dict(self.script[idx])
        if idx in self.fail_at:
            reply = {"thought": "deliberate fault injection", "tool": "__fault__", "args": {}}
        latency = int((time.perf_counter() - start) * 1000)
        text = json.dumps(reply)
        usd = 0.0 if tier == "cheap" else 0.0
        return parse_reply(text, model=f"offline:{tier}", usd=usd, tokens=len(text) // 4, latency_ms=latency)


class OllamaLLM:
    """Local models through Ollama's OpenAI-compatible endpoint."""

    name = "ollama"

    def __init__(self, cheap: str = "qwen2.5-coder:3b", strong: str = "qwen2.5-coder:7b",
                 base_url: str = "http://127.0.0.1:11434", timeout: float = 120.0,
                 usd_per_1k_cheap: float = 0.0, usd_per_1k_strong: float = 0.0):
        self.cheap = cheap
        self.strong = strong
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.usd_per_1k_cheap = usd_per_1k_cheap
        self.usd_per_1k_strong = usd_per_1k_strong

    def describe(self) -> str:
        return f"ollama(cheap={self.cheap}, strong={self.strong})"

    def complete(self, messages: list[dict[str, str]], tier: str, tools: list[str]) -> LLMReply:
        import httpx

        model = self.cheap if tier == "cheap" else self.strong
        system = TOOL_PROTOCOL + "\nAvailable tools: " + ", ".join(sorted(tools)) + "\n"
        body = {
            "model": model,
            "messages": chat_messages([{"role": "system", "content": system}] + messages),
            "stream": False,
            "options": {"temperature": 0.0},
        }
        started = time.perf_counter()
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=body)
            resp.raise_for_status()
            data = resp.json()
        latency = int((time.perf_counter() - started) * 1000)
        text = (data.get("message") or {}).get("content", "")
        tokens = int(data.get("eval_count", 0)) + int(data.get("prompt_eval_count", 0))
        rate = self.usd_per_1k_cheap if tier == "cheap" else self.usd_per_1k_strong
        return parse_reply(text, model=model, usd=rate * tokens / 1000.0, tokens=tokens, latency_ms=latency)


class OpenAICompatibleLLM:
    """Any /v1/chat/completions endpoint."""

    name = "openai"

    def __init__(self, cheap: str, strong: str, base_url: str, api_key: str = "not-needed",
                 timeout: float = 120.0, usd_per_1k_cheap: float = 0.0, usd_per_1k_strong: float = 0.0):
        self.cheap = cheap
        self.strong = strong
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.usd_per_1k_cheap = usd_per_1k_cheap
        self.usd_per_1k_strong = usd_per_1k_strong

    def describe(self) -> str:
        return f"openai(cheap={self.cheap}, strong={self.strong}, base={self.base_url})"

    def complete(self, messages: list[dict[str, str]], tier: str, tools: list[str]) -> LLMReply:
        import httpx

        model = self.cheap if tier == "cheap" else self.strong
        system = TOOL_PROTOCOL + "\nAvailable tools: " + ", ".join(sorted(tools)) + "\n"
        body = {
            "model": model,
            "messages": chat_messages([{"role": "system", "content": system}] + messages),
            "temperature": 0.0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }
        started = time.perf_counter()
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        latency = int((time.perf_counter() - started) * 1000)
        text = data["choices"][0]["message"].get("content", "")
        tokens = int((data.get("usage") or {}).get("total_tokens", 0))
        rate = self.usd_per_1k_cheap if tier == "cheap" else self.usd_per_1k_strong
        return parse_reply(text, model=model, usd=rate * tokens / 1000.0, tokens=tokens, latency_ms=latency)


def make_llm(opts: dict[str, Any]) -> LLMClient:
    """Build an LLM client from harness options."""
    mode = str(opts.get("model_mode", "offline"))
    if mode == "offline":
        return OfflineLLM(script=opts.get("offline_script"), fail_at=opts.get("fail_at"))
    if mode == "ollama":
        return OllamaLLM(
            cheap=opts.get("model_cheap", "qwen2.5-coder:3b"),
            strong=opts.get("model_strong", "qwen2.5-coder:7b"),
            base_url=opts.get("base_url", "http://127.0.0.1:11434"),
        )
    if mode in ("openai", "odyssey"):
        return OpenAICompatibleLLM(
            cheap=opts.get("model_cheap", "openai/gpt-4o"),
            strong=opts.get("model_strong", "openai/gpt-4o"),
            base_url=opts.get("base_url") or default_llm_base_url(),
            api_key=opts.get("api_key") or default_llm_api_key(),
        )
    raise ValueError(f"unknown model_mode {mode!r} (expected offline|ollama|openai|odyssey)")


def default_llm_base_url() -> str:
    import os

    if os.environ.get("ODYSSEY_API_KEY"):
        return (os.environ.get("ODYSSEY_BASE_URL") or "https://odysseyapi.tech/v1").rstrip("/")
    return "http://127.0.0.1:1234/v1"


def default_llm_api_key() -> str:
    import os

    return os.environ.get("ODYSSEY_API_KEY") or os.environ.get("OPENAI_API_KEY") or "lm-studio"


def make_odyssey_openai_client():
    """OpenAI SDK client for Odyssey, with LM Studio fallback. Keys from os.environ only."""
    import os

    from openai import OpenAI

    key = os.environ.get("ODYSSEY_API_KEY")
    if key:
        base = (os.environ.get("ODYSSEY_BASE_URL") or "https://odysseyapi.tech/v1").rstrip("/")
        return OpenAI(base_url=base, api_key=key)
    return OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")