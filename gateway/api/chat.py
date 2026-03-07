from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter()


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: Optional[int] = None
    remember: bool = True
    max_steps: int = 6


class QueryResponse(BaseModel):
    session_id: int
    answer: str
    meta: Dict[str, Any]
    memories: list[Dict[str, Any]] = []
    debug_log: str = ""


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, request: Request) -> QueryResponse:
    result = request.app.state.container.agent.run(
        query=req.query,
        session_id=req.session_id,
        remember=req.remember,
        max_steps=req.max_steps,
    )
    return QueryResponse(**result)
