from __future__ import annotations

import time
from typing import Dict, List, Tuple

import requests


class OpenAIChatClient:
    """Chat client compatible with OpenAI API.

    Supports both Chat Completions and Responses API. The Responses API path is
    needed for Codex-tuned models such as gpt-5.3-codex.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
        api_mode: str = "chat_completions",
        reasoning_effort: str | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_mode = (api_mode or "chat_completions").lower()
        self.reasoning_effort = reasoning_effort

    def complete_json(self, messages: List[Dict[str, str]]) -> Tuple[str, float]:
        if self.api_mode == "responses":
            return self._complete_json_responses(messages)
        return self._complete_json_chat_completions(messages)

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _map_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        mapped = []
        for m in messages:
            role = m["role"]
            if role == "tool":
                mapped.append({"role": "user", "content": f"[Tool result]: {m['content']}"})
            else:
                mapped.append({"role": role, "content": m["content"]})
        return mapped

    def _complete_json_chat_completions(self, messages: List[Dict[str, str]]) -> Tuple[str, float]:
        t0 = time.perf_counter()
        payload = {
            "model": self.model,
            "messages": self._map_messages(messages),
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        r = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=self._auth_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return content, (time.perf_counter() - t0)

    def _complete_json_responses(self, messages: List[Dict[str, str]]) -> Tuple[str, float]:
        t0 = time.perf_counter()
        payload = {
            "model": self.model,
            "input": self._map_messages(messages),
            "store": False,
            "text": {
                "format": {
                    "type": "json_object",
                }
            },
        }
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}

        r = requests.post(
            f"{self.base_url}/responses",
            json=payload,
            headers=self._auth_headers(),
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        content = data.get("output_text")
        if not content:
            parts = []
            for item in data.get("output", []):
                for block in item.get("content", []):
                    text = block.get("text")
                    if text:
                        parts.append(text)
            content = "".join(parts)
        return content or "{}", (time.perf_counter() - t0)


class OpenAIEmbeddingsClient:
    """Embeddings client compatible with OpenAI API."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small",
                 base_url: str = "https://api.openai.com/v1",
                 timeout: float = 120.0):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def embed(self, text: str) -> Tuple[List[float], float]:
        t0 = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        r = requests.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": text},
            headers=headers,
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        embedding = data["data"][0]["embedding"]
        return embedding, (time.perf_counter() - t0)
