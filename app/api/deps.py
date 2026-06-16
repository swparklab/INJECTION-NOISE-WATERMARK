"""Shared FastAPI dependencies and singletons."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core.watermark_engine import WatermarkService
from app.db.base import get_session

_service: WatermarkService | None = None


def get_watermark_service() -> WatermarkService:
    """Return a process-wide WatermarkService singleton."""
    global _service
    if _service is None:
        _service = WatermarkService()
    return _service


def db_session() -> Iterator[Session]:
    """Yield a database session (FastAPI dependency)."""
    yield from get_session()
