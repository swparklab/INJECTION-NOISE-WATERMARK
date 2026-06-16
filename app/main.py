"""FastAPI application entrypoint for the Injection Noise Watermark platform.

Wires together all routers (embed, detect, trace, remove, provenance/evidence,
models) and initialises the engine registry + database at startup.

Run locally:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import detect, embed, models, remove, trace, verify
from app.config.settings import get_settings
from app.core import registry as engine_registry
from app.db.base import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise database tables and register engines on startup."""
    settings = get_settings()
    settings.ensure_dirs()
    init_db()
    engine_registry.register_builtin_engines()
    _seed_models()
    logger.info("Platform ready: models=%s", engine_registry.available_models())
    yield


def _seed_models() -> None:
    """Populate the watermark_models registry table from available engines."""
    from app.db.base import session_scope
    from app.provenance.registry import RegistryService

    descriptions = {
        "custom-noise": ("Custom Noise Engine", ["image", "video"]),
        "frequency": ("Frequency Watermark", ["image"]),
        "videoseal": ("VideoSeal", ["video", "image"]),
        "metaseal": ("Meta Seal", ["image", "video"]),
        "invismark": ("InvisMark", ["image"]),
        "wam": ("Watermark Anything", ["image"]),
        "tree-ring": ("Tree-Ring", ["image"]),
        "gaussian-shading": ("Gaussian Shading", ["image"]),
        "ringid": ("RingID", ["image"]),
    }
    try:
        with session_scope() as session:
            reg = RegistryService(session)
            for mid in engine_registry.available_models():
                name, media_types = descriptions.get(mid, (mid, ["image"]))
                reg.upsert_model(mid, name, media_types)
    except Exception as exc:  # noqa: BLE001
        logger.warning("model seeding skipped: %s", exc)


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description="Enterprise invisible-watermark platform: embed, detect, trace, remove, verify.",
        lifespan=lifespan,
    )

    prefix = settings.api_v1_prefix
    app.include_router(embed.router, prefix=prefix)
    app.include_router(detect.router, prefix=prefix)
    app.include_router(trace.router, prefix=prefix)
    app.include_router(remove.router, prefix=prefix)
    app.include_router(verify.router, prefix=prefix)
    app.include_router(models.router, prefix=prefix)

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        """Liveness probe."""
        return {"status": "ok", "models": engine_registry.available_models()}

    @app.get("/", tags=["health"])
    async def root() -> dict:
        """Root info."""
        return {
            "name": settings.app_name,
            "version": "0.2.0",
            "docs": "/docs",
            "api": prefix,
        }

    return app


app = create_app()
