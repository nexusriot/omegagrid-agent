from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class NewSessionResponse(BaseModel):
    session_id: int


class SessionsResponse(BaseModel):
    sessions: list[Dict[str, Any]]


class MessagesResponse(BaseModel):
    session_id: int
    messages: list[Dict[str, Any]]


@router.post("/sessions/new", response_model=NewSessionResponse)
def new_session(request: Request) -> NewSessionResponse:
    sid = request.app.state.container.history.create_session()
    return NewSessionResponse(session_id=sid)


@router.get("/sessions", response_model=SessionsResponse)
def list_sessions(request: Request, limit: int = 50) -> SessionsResponse:
    return SessionsResponse(sessions=request.app.state.container.history.list_sessions(limit=limit))


@router.get("/sessions/{session_id}/messages", response_model=MessagesResponse)
def session_messages(session_id: int, request: Request, limit: int = 200, offset: int = 0) -> MessagesResponse:
    try:
        rows = request.app.state.container.history.list_messages(session_id=session_id, limit=limit, offset=offset)
        return MessagesResponse(session_id=session_id, messages=rows)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
