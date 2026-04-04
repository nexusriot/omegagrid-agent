from __future__ import annotations

import time
from typing import List, Tuple

import requests


class OllamaEmbeddingsClient:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, text: str) -> Tuple[List[float], float]:
        t0 = time.perf_counter()
        base = self.base_url

        r = requests.post(
            f"{base}/api/embed",
            json={"model": self.model, "input": text},
            timeout=self.timeout,
        )
        if r.status_code == 200:
            data = r.json()
            embs = data.get("embeddings")
            if isinstance(embs, list) and embs and isinstance(embs[0], list) and embs[0]:
                return embs[0], (time.perf_counter() - t0)

        r = requests.post(
            f"{base}/v1/embeddings",
            json={"model": self.model, "input": text},
            timeout=self.timeout,
        )
        if r.status_code == 200:
            data = r.json()
            arr = data.get("data")
            if isinstance(arr, list) and arr and isinstance(arr[0], dict) and isinstance(arr[0].get("embedding"), list):
                return arr[0]["embedding"], (time.perf_counter() - t0)

        r = requests.post(
            f"{base}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        emb = data.get("embedding")
        if not isinstance(emb, list) or not emb:
            raise RuntimeError("Embeddings endpoint returned empty embedding")
        return emb, (time.perf_counter() - t0)
