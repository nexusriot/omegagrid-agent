from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings


class VectorStore:
    def __init__(self, persist_dir: str, collection_name: str, embeddings_client, dedup_distance: float = 0.08):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embeddings_client = embeddings_client
        self.dedup_distance = dedup_distance

        os.makedirs(self.persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.col = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _sanitize_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in (meta or {}).items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                out[k] = v
            else:
                out[k] = json.dumps(v, ensure_ascii=False)
        return out

    def add_text(self, text: str, meta: Optional[Dict[str, Any]] = None, memory_id: Optional[str] = None) -> Dict[str, Any]:
        timings: Dict[str, float] = {}
        text = (text or "").strip()
        if not text:
            raise ValueError("text is empty")

        h = self._hash_text(text)
        mid = memory_id or str(uuid.uuid4())
        meta = dict(meta or {})
        meta.setdefault("created_at", time.time())
        meta["hash"] = h
        safe_meta = self._sanitize_meta(meta)

        t0 = time.perf_counter()
        existing = self.col.get(where={"hash": h}, include=["documents", "metadatas"])
        timings["chroma_get_s"] = time.perf_counter() - t0
        if existing and existing.get("ids"):
            return {
                "memory_id": existing["ids"][0],
                "skipped": True,
                "reason": "exact_hash_duplicate",
                "timings": timings,
            }

        emb, emb_s = self.embeddings_client.embed(text)
        timings["ollama_embed_s"] = emb_s

        t1 = time.perf_counter()
        q = self.col.query(query_embeddings=[emb], n_results=1, include=["distances"])
        timings["chroma_query_s"] = time.perf_counter() - t1

        nearest_dist = None
        if q and q.get("distances") and q["distances"][0]:
            nearest_dist = float(q["distances"][0][0])
            if nearest_dist <= self.dedup_distance:
                return {
                    "memory_id": q["ids"][0][0],
                    "skipped": True,
                    "reason": "semantic_duplicate",
                    "nearest_distance": nearest_dist,
                    "timings": timings,
                }

        t2 = time.perf_counter()
        self.col.add(ids=[mid], documents=[text], embeddings=[emb], metadatas=[safe_meta])
        timings["chroma_add_s"] = time.perf_counter() - t2

        return {
            "memory_id": mid,
            "skipped": False,
            "reason": "",
            "nearest_distance": nearest_dist,
            "timings": timings,
        }

    def search_text(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        hits, _ = self.search_with_timings(query, k=k)
        return hits

    def search_with_timings(self, query: str, k: int = 5) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        timings: Dict[str, float] = {}
        query = (query or "").strip()
        if not query:
            return [], timings

        t0 = time.perf_counter()
        emb, emb_s = self.embeddings_client.embed(query)
        timings["ollama_embed_s"] = emb_s

        t1 = time.perf_counter()
        res = self.col.query(
            query_embeddings=[emb],
            n_results=max(1, int(k)),
            include=["documents", "metadatas", "distances"],
        )
        timings["chroma_query_s"] = time.perf_counter() - t1
        timings["vector_search_total_s"] = time.perf_counter() - t0

        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        ids = (res.get("ids") or [[]])[0]

        hits: List[Dict[str, Any]] = []
        for mid, doc, meta, dist in zip(ids, docs, metas, dists):
            hits.append({
                "id": mid,
                "text": doc,
                "metadata": meta,
                "distance": float(dist),
            })
        return hits, timings
