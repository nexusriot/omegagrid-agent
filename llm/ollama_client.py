from __future__ import annotations

import time
from typing import Dict, List, Tuple

import requests


class OllamaChatClient:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete_json(self, messages: List[Dict[str, str]]) -> Tuple[str, float]:
        t0 = time.perf_counter()
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        }
        r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"], (time.perf_counter() - t0)
