"""
api/main.py
FastAPI application factory, lifespan management, middleware, and route mounting.

Spec references:
  §3.1 — FastAPI behind existing gateway; SQLAlchemy 2.0 async + asyncpg; Redis
  Phase 1.1 — FastAPI app with lifespan, health endpoint, settings integration
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes.admin import router as admin_router
from api.routes.config import router as config_router
from api.routes.trade_name import router as trade_name_router
from config.settings import get_settings
from db.models import Base
from db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager for startup and shutdown events.
    """
    # Startup: ensure DB engine can initialize and tables exist
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass
    yield
    # Shutdown: dispose DB engine cleanly
    await engine.dispose()


def create_app() -> FastAPI:
    """
    App factory creating and configuring the FastAPI instance.
    """
    app = FastAPI(
        title="Trade Name Intelligence Service",
        description="Auditable AI-assisted validation pipeline for Arabic and English trade names (DED UAQ)",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(trade_name_router)
    app.include_router(admin_router)
    app.include_router(config_router)

    @app.get("/health", tags=["System"])
    async def health_check():
        """Health check endpoint returning service status and active flags."""
        return {
            "status": "healthy",
            "service": settings.service_name,
            "environment": settings.environment,
            "feature_flags": {
                "ai_analyzer": settings.ai_analyzer.value,
                "ai_suggestions": settings.ai_suggestions.value,
                "ai_reviewer_brief": settings.ai_reviewer_brief.value,
                "ai_search": settings.ai_search.value,
                "ai_lexicon_proposals": settings.ai_lexicon_proposals.value,
            },
        }

    @app.get("/ready", tags=["System"])
    async def readiness_check():
        """Readiness check endpoint."""
        return {"status": "ready"}

    @app.get("/metrics", tags=["System"], summary="Prometheus metrics (Phase 6, N2)")
    async def get_metrics():
        """Scrape endpoint for Prometheus monitoring."""
        from api.metrics import metrics_endpoint
        return metrics_endpoint()

    # Mount static demo frontend if available
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import RedirectResponse

    frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/demo", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

        @app.get("/", include_in_schema=False)
        async def root_redirect():
            return RedirectResponse(url="/demo/")

    return app


app = create_app()
