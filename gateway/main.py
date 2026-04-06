import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.dependencies import build_container
from gateway.api.chat import router as chat_router
from gateway.api.history import router as history_router
from gateway.api.memory import router as memory_router
from gateway.api.health import router as health_router
from gateway.api.tools import router as tools_router
from gateway.api.skills import router as skills_router
from gateway.api.scheduler import router as scheduler_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start the scheduler background thread
    container = app.state.container
    if container.scheduler_runner:
        container.scheduler_runner.start()
        logger.info("Scheduler runner started")
    yield
    # Shutdown: stop the scheduler
    if container.scheduler_runner:
        container.scheduler_runner.stop()
        logger.info("Scheduler runner stopped")


container = build_container()

app = FastAPI(title="OmegaGrid Agent Gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.container = container
app.state.scheduler_store = container.scheduler_store

app.include_router(chat_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(tools_router, prefix="/api")
app.include_router(skills_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")
app.include_router(health_router)
