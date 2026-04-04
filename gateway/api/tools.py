from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/tools")
def list_tools(request: Request) -> dict:
    return {"tools": request.app.state.container.tools.describe()}
