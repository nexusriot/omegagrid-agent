import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: Optional[int] = None
    remember: bool = True
    max_steps: int = 10
    telegram_chat_id: Optional[int] = None


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
            telegram_chat_id=req.telegram_chat_id,
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


@router.post("/query/stream")
def query_stream(req: QueryRequest, request: Request):
    """SSE streaming endpoint — yields events as the agent works."""

    def _generate():
        try:
            for event in request.app.state.container.agent.run_stream(
                query=req.query,
                session_id=req.session_id,
                remember=req.remember,
                max_steps=req.max_steps,
                telegram_chat_id=req.telegram_chat_id,
            ):
                yield {"event": event.get("event", "message"), "data": json.dumps(event, ensure_ascii=False)}
        except Exception as e:
            logger.exception("Agent stream failed")
            yield {"event": "error", "data": json.dumps({"event": "error", "error": str(e)})}

    return EventSourceResponse(_generate())
