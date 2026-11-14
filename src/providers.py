"""Chat Completions providers behind one interface, adapted from the Day 4 lab's providers.py.

Day 4 repo: TheDLCrimson/K5-L3B-DAY04-LuuNguyenChiDuc-2A202603923-ReactLoopAgent. Changes here:
only the OpenAI-compatible providers are kept (this lab runs on OpenRouter), OpenRouter is
asked to report the real cost of every call, and each call returns its wall-clock time.

`complete(messages, tools)` returns {message, calls, finish, usage, ms}. Failures raise
ProviderError with the HTTP status or network reason, never the response body, which may
hold account data; nothing is retried silently.
"""
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from dotenv import load_dotenv

from .day6 import REPO_ROOT

CONFIG = {
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1/chat/completions"),
    "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1/chat/completions"),
    "gemini": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"),
}
MAX_TOKENS = 4096
TIMEOUT_S = 120


class ProviderError(RuntimeError):
    """The model call failed; the agent records it as an error, not as an answer."""


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"provider returned HTTP {exc.code}; check model, key and credits") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"cannot reach provider: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ProviderError(f"provider timed out after {TIMEOUT_S} s") from exc


class Provider:
    def __init__(self, name: str | None = None, model: str | None = None) -> None:
        load_dotenv(REPO_ROOT / ".env")
        self.name = name or os.environ.get("PROVIDER", "")
        self.model = model or os.environ.get("MODEL", "")
        if self.name not in CONFIG:
            raise ValueError(f"unknown provider {self.name!r}; set PROVIDER in .env")
        if not self.model:
            raise ValueError("set MODEL in .env to a model with tool calling")
        key_name, self.url = CONFIG[self.name]
        self.key = os.environ.get(key_name)
        if not self.key:
            raise ValueError(f"{key_name} is not set; see .env.example")

    def describe(self) -> dict[str, str]:
        return {"provider": self.name, "model": self.model}

    def complete(self, messages: list[dict], tools: list[dict]) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "max_tokens": MAX_TOKENS}
        if tools:
            payload["tools"] = tools
        if self.name == "openrouter":
            payload["usage"] = {"include": True}  # adds the billed cost in USD to `usage`
        start = time.perf_counter()
        data = post_json(self.url, {"Authorization": f"Bearer {self.key}"}, payload)
        ms = round((time.perf_counter() - start) * 1000, 1)
        if "choices" not in data or not data["choices"]:
            raise ProviderError(f"provider returned no choices (keys: {sorted(data)})")
        choice = data["choices"][0]
        message = choice["message"]
        calls = [{"id": c["id"], "name": c["function"]["name"], "arguments": c["function"]["arguments"]}
                 for c in message.get("tool_calls") or []]
        return {"message": message, "calls": calls, "finish": choice.get("finish_reason"),
                "usage": data.get("usage", {}), "ms": ms, "model": data.get("model", self.model)}
