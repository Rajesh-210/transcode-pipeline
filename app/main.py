"""Transcoding Pipeline API Service - FastAPI."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.redis import get_redis, close_redis
from app.core.middleware import register_middleware
from app.api.v1.router import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    settings = get_settings()
    # Ensure Redis connection can be created
    await get_redis()
    yield
    # Cleanup Redis
    await close_redis()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        description="Production Event-Driven Media Transcoding Pipeline API",
        version=settings.api_version,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register observability and middleware
    register_middleware(app)

    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint returning service status."""
        return {
            "service": settings.api_title,
            "version": settings.api_version,
            "status": "online",
            "docs_url": "/docs",
        }

    @app.get("/healthz", tags=["health"])
    async def health_check():
        """Liveness / health check endpoint for Docker & Kubernetes."""
        return {"status": "healthy"}

    return app


app = create_app()
