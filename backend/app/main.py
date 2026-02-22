from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .sqlite_memory import MemoryDB
from .vector_memory import VectorMemory
from .agent import run_agent_query

APP_TITLE = "Ollama Agent (SQLite + Vector Memory)"
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
SQLITE_PATH = os.environ.get("AGENT_DB", os.path.join(DATA_DIR, "agent_memory.sqlite3"))
VECTOR_DIR = os.environ.get("AGENT_VECTOR_DIR", os.path.join(DATA_DIR, "vector_db"))
VECTOR_COLLECTION = os.environ.get("AGENT_VECTOR_COLLECTION", "memories")
CONTEXT_TAIL = int(os.environ.get("AGENT_CONTEXT_TAIL", "30"))
MEMORY_HITS = int(os.environ.get("AGENT_MEMORY_HITS", "5"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3:latest")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "120"))
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
DEDUP_DISTANCE = float(os.environ.get("AGENT_DEDUP_DISTANCE", "0.08"))


app = FastAPI(title=APP_TITLE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

mem = MemoryDB(SQLITE_PATH)
vmem = VectorMemory(
    persist_dir=VECTOR_DIR,
    collection_name=VECTOR_COLLECTION,
    ollama_url=OLLAMA_URL,
    embed_model=OLLAMA_EMBED_MODEL,
    timeout=OLLAMA_TIMEOUT,
    dedup_distance=DEDUP_DISTANCE,
)

class QueryReq(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: Optional[int] = None
    remember: bool = True  # allow agent to store durable memories
    max_steps: int = 6


class QueryResp(BaseModel):
    session_id: int
    answer: str
    meta: Dict[str, Any]
    memories: list[Dict[str, Any]] = []
    debug_log: str = ""


class NewSessionResp(BaseModel):
    session_id: int


class SessionsResp(BaseModel):
    sessions: list[Dict[str, Any]]


class MemoryAddReq(BaseModel):
    text: str = Field(..., min_length=1)
    meta: Dict[str, Any] = Field(default_factory=dict)


class MemoryAddResp(BaseModel):
    ok: bool
    memory_id: str
    skipped: bool = False
    reason: str = ""


class MemorySearchReq(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = 5


class MemorySearchResp(BaseModel):
    ok: bool
    hits: list[Dict[str, Any]]


class MessagesResp(BaseModel):
    session_id: int
    messages: list[Dict[str, Any]]


@app.get("/api/sessions/{session_id}/messages", response_model=MessagesResp)
def session_messages(session_id: int, limit: int = 200, offset: int = 0) -> MessagesResp:
    try:
        msgs = mem.list_messages(session_id=session_id, limit=limit, offset=offset)
        return MessagesResp(session_id=session_id, messages=msgs)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "ollama_url": OLLAMA_URL,
        "ollama_model": OLLAMA_MODEL,
        "embed_model": OLLAMA_EMBED_MODEL,
        "sqlite": SQLITE_PATH,
        "vector_dir": VECTOR_DIR,
    }


@app.post("/api/sessions/new", response_model=NewSessionResp)
def new_session() -> NewSessionResp:
    sid = mem.create_session()
    return NewSessionResp(session_id=sid)


@app.get("/api/sessions", response_model=SessionsResp)
def list_sessions(limit: int = 50) -> SessionsResp:
    return SessionsResp(sessions=mem.list_sessions(limit=limit))


@app.post("/api/memory/add", response_model=MemoryAddResp)
def memory_add(req: MemoryAddReq) -> MemoryAddResp:
    try:
        out = vmem.add(text=req.text, meta=req.meta)
        return MemoryAddResp(ok=True, memory_id=out["memory_id"], skipped=out["skipped"], reason=out["reason"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/memory/search", response_model=MemorySearchResp)
def memory_search(req: MemorySearchReq) -> MemorySearchResp:
    try:
        hits = vmem.search(query=req.query, k=req.k)
        return MemorySearchResp(ok=True, hits=hits)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/query", response_model=QueryResp)
def query(req: QueryReq) -> QueryResp:
    # Session
    sid = req.session_id if req.session_id is not None else mem.create_session()

    # Run agent
    t0 = time.perf_counter()
    answer, meta, memories, debug_log = run_agent_query(
        query=req.query,
        session_id=sid,
        mem=mem,
        vmem=vmem,
        context_tail=CONTEXT_TAIL,
        memory_hits=MEMORY_HITS,
        ollama_url=OLLAMA_URL,
        ollama_model=OLLAMA_MODEL,
        ollama_timeout=OLLAMA_TIMEOUT,
        max_steps=req.max_steps,
        allow_remember=req.remember,
    )
    meta["timings_total_s"] = round(time.perf_counter() - t0, 6)

    return QueryResp(
        session_id=sid,
        answer=answer,
        meta=meta,
        memories=memories,
        debug_log=debug_log,
    )
