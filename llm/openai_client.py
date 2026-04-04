from __future__ import annotations

import time
from typing import Dict, List, Tuple

import requests


class OpenAIChatClient:
    """Chat client compatible with OpenAI API (works with OpenAI, Azure, any compatible endpoint)."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini",
                 base_url: str = "https://api.openai.com/v1",
                 timeout: float = 120.0):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete_json(self, messages: List[Dict[str, str]]) -> Tuple[str, float]:
        t0 = time.perf_counter()
        # Map 'tool' role to 'user' (OpenAI doesn't support arbitrary 'tool' role without tool_call_id)
        mapped = []
        for m in messages:
            role = m["role"]
            if role == "tool":
                mapped.append({"role": "user", "content": f"[Tool result]: {m['content']}"})
            else:
                mapped.append({"role": role, "content": m["content"]})

        payload = {
            "model": self.model,
            "messages": mapped,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        r = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return content, (time.perf_counter() - t0)


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
