"""Create the FastAPI application and load the in-memory index at startup."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router
from backend.app.services.index_construction import rebuild_index

FRONTEND_DIRECTORY = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Rebuild index state from stored documents whenever the API starts."""
    rebuild_index()
    yield

app = FastAPI(
    title="Intelligent Multi-Pattern Search & Document Analytics Engine",
    description="API for document ingestion and inverted-index construction.",
    lifespan=lifespan,
)

app.include_router(router)
app.mount("/ui", StaticFiles(directory=FRONTEND_DIRECTORY, html=True), name="analytics-ui")