import os

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    container = request.app.state.container
    return {
        "ok": True,
        "ollama_url": container.chat.base_url,
        "ollama_model": container.chat.model,
        "embed_model": container.embed.model,
        "sqlite": os.environ.get("AGENT_DB", "/app/data/agent_memory.sqlite3"),
        "vector_dir": os.environ.get("AGENT_VECTOR_DIR", "/app/data/vector_db"),
    }
