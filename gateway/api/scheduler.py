from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter()


class CreateTaskRequest(BaseModel):
    name: str = Field(..., min_length=1)
    cron_expr: str = Field(..., min_length=5, description="5-field cron expression")
    skill: str = Field(..., min_length=1)
    args: Dict[str, Any] = {}
    notify_telegram_chat_id: Optional[int] = None


class TaskResponse(BaseModel):
    id: int
    name: str
    cron_expr: str
    skill: str
    args: Dict[str, Any]
    notify_telegram_chat_id: Optional[int]
    enabled: bool
    created_at: float
    last_run_at: Optional[float]
    last_result: Optional[str]
    run_count: int


@router.post("/scheduler/tasks", response_model=TaskResponse)
def create_task(req: CreateTaskRequest, request: Request):
    store = request.app.state.scheduler_store
    task = store.create(
        name=req.name,
        cron_expr=req.cron_expr,
        skill=req.skill,
        args=req.args,
        notify_telegram_chat_id=req.notify_telegram_chat_id,
    )
    return TaskResponse(**task.to_dict())


@router.get("/scheduler/tasks", response_model=List[TaskResponse])
def list_tasks(request: Request):
    store = request.app.state.scheduler_store
    return [TaskResponse(**t.to_dict()) for t in store.list_all()]


@router.get("/scheduler/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, request: Request):
    store = request.app.state.scheduler_store
    task = store.get(task_id)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    return TaskResponse(**task.to_dict())


@router.post("/scheduler/tasks/{task_id}/enable")
def enable_task(task_id: int, request: Request):
    store = request.app.state.scheduler_store
    if store.set_enabled(task_id, True):
        return {"ok": True, "task_id": task_id, "enabled": True}
    return {"ok": False, "error": "Task not found"}


@router.post("/scheduler/tasks/{task_id}/disable")
def disable_task(task_id: int, request: Request):
    store = request.app.state.scheduler_store
    if store.set_enabled(task_id, False):
        return {"ok": True, "task_id": task_id, "enabled": False}
    return {"ok": False, "error": "Task not found"}


@router.delete("/scheduler/tasks/{task_id}")
def delete_task(task_id: int, request: Request):
    store = request.app.state.scheduler_store
    if store.delete(task_id):
        return {"ok": True, "task_id": task_id}
    return {"ok": False, "error": "Task not found"}
