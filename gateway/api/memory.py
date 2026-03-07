from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


class MemoryAddRequest(BaseModel):
    text: str = Field(..., min_length=1)
    meta: Dict[str, Any] = Field(default_factory=dict)


class MemoryAddResponse(BaseModel):
    ok: bool
    memory_id: str
    skipped: bool = False
    reason: str = ""


class MemorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = 5


class MemorySearchResponse(BaseModel):
    ok: bool
    hits: list[Dict[str, Any]]


@router.post("/memory/add", response_model=MemoryAddResponse)
def add_memory(req: MemoryAddRequest, request: Request) -> MemoryAddResponse:
    try:
        out = request.app.state.container.vector.add_text(req.text, req.meta)
        return MemoryAddResponse(ok=True, memory_id=str(out["memory_id"]), skipped=out.get("skipped", False), reason=out.get("reason", ""))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/memory/search", response_model=MemorySearchResponse)
def search_memory(req: MemorySearchRequest, request: Request) -> MemorySearchResponse:
    try:
        hits = request.app.state.container.vector.search_text(req.query, k=req.k)
        return MemorySearchResponse(ok=True, hits=hits)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
