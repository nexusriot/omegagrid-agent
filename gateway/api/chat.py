import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

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
def query(req: QueryRequest, request: Request):
    try:
        result = request.app.state.container.agent.run(
            query=req.query,
            session_id=req.session_id,
            remember=req.remember,
            max_steps=req.max_steps,
        )
        return QueryResponse(**result)
    except Exception as e:
        logger.exception("Agent run failed")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "hint": "Check that your LLM and embedding models are available and running.",
            },
        )
