from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/skills")
def list_skills(request: Request) -> dict:
    return {"skills": request.app.state.container.skills.describe()}
