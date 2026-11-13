"""API process: `uvicorn app.api.main:app`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.feed_routes import router as feed_router
from app.api.routes import router
from app.config import Settings, get_settings
from app.db import make_engine, make_sessionmaker
from app.feed.repository import FeedRepository
from app.jobs.repository import JobRepository
from app.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        engine = make_engine(settings.database_url)
        app.state.settings = settings
        app.state.engine = engine
        sessionmaker = make_sessionmaker(engine)
        app.state.repo = JobRepository(sessionmaker)
        app.state.feed_repo = FeedRepository(sessionmaker)
        yield
        await engine.dispose()

    app = FastAPI(title="TechPulse", version="0.2.0", lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["*"]
        )
    app.include_router(feed_router)
    if settings.enable_legacy_jobs_api:
        app.include_router(router)  # legacy mock research jobs (no AI)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness: the process is up (no database access)."""
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready(request: Request) -> JSONResponse:
        """Readiness: the database is reachable. Use for platform health checks."""
        try:
            async with request.app.state.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError):
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"})

    return app


app = create_app()
