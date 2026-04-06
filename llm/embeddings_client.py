from __future__ import annotations

import logging
import time
from typing import List, Tuple

import requests

logger = logging.getLogger(__name__)


class OllamaEmbeddingsClient:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, text: str) -> Tuple[List[float], float]:
        t0 = time.perf_counter()
        base = self.base_url
        errors: list[str] = []

        # Attempt 1: /api/embed (native Ollama)
        try:
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
            errors.append(f"/api/embed: status={r.status_code} body={r.text[:200]}")
        except requests.exceptions.RequestException as e:
            errors.append(f"/api/embed: {e}")

        # Attempt 2: /v1/embeddings (OpenAI-compatible)
        try:
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
            errors.append(f"/v1/embeddings: status={r.status_code} body={r.text[:200]}")
        except requests.exceptions.RequestException as e:
            errors.append(f"/v1/embeddings: {e}")

        # Attempt 3: /api/embeddings (legacy)
        try:
            r = requests.post(
                f"{base}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=self.timeout,
            )
            if r.status_code == 200:
                data = r.json()
                emb = data.get("embedding")
                if isinstance(emb, list) and emb:
                    return emb, (time.perf_counter() - t0)
            errors.append(f"/api/embeddings: status={r.status_code} body={r.text[:200]}")
        except requests.exceptions.RequestException as e:
            errors.append(f"/api/embeddings: {e}")

        detail = "; ".join(errors)
        logger.error("All embedding endpoints failed for model=%s: %s", self.model, detail)
        raise RuntimeError(
            f"All embedding endpoints failed (model={self.model}, base={base}). "
            f"Ensure the embedding model is pulled and available. Errors: {detail}"
        )
