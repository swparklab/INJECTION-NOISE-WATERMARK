"""Shared pytest fixtures for app/ platform tests."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def natural_image() -> np.ndarray:
    """A deterministic natural-looking 512x512 RGB image (1/f-ish spectrum).

    Random uniform noise is unrealistically hostile to watermarks; real photos
    and video frames concentrate energy in low frequencies. This fixture mimics
    that so robustness numbers reflect real deployment conditions.
    """
    import cv2

    rng = np.random.default_rng(20260617)
    size = 512
    base = np.zeros((size, size, 3), np.float32)
    xs = np.linspace(0, 1, size)
    base += (np.outer(xs, np.ones(size)) * 120 + 60)[..., None]
    for _ in range(6):
        cx, cy = rng.integers(0, size, 2)
        r = rng.integers(40, 180)
        col = rng.integers(0, 255, 3).astype(np.float32)
        yy, xx = np.ogrid[:size, :size]
        m = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r))
        base += m[..., None] * (col - base.mean(axis=(0, 1))) * 0.6
    base = cv2.GaussianBlur(base + rng.normal(0, 4, base.shape), (3, 3), 0)
    return np.clip(base, 0, 255).astype(np.uint8)


@pytest.fixture
def jpeg():
    """Return a helper that JPEG-recompresses an RGB image at a given quality."""
    import cv2

    def _jpeg(image: np.ndarray, quality: int = 75) -> np.ndarray:
        ok, enc = cv2.imencode(
            ".jpg", cv2.cvtColor(image, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality]
        )
        return cv2.cvtColor(cv2.imdecode(enc, 1), cv2.COLOR_BGR2RGB)

    return _jpeg


@pytest.fixture
def key() -> bytes:
    """A fixed 32-byte secret key for engine tests."""
    return b"k" * 32


@pytest.fixture
def registered_engines():
    """Ensure built-in engines + adapters are registered once per session."""
    from app.core import registry as er

    er.register_builtin_engines()
    return er


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    """Provide an isolated SQLite DB per test by pointing settings at tmp_path.

    Rebuilds the SQLAlchemy engine/session bound to the temp DB so tests do not
    touch the developer's local registry.
    """
    import app.db.base as dbbase
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = f"sqlite:///{tmp_path / 'test_registry.db'}"
    engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False})
    monkeypatch.setattr(dbbase, "engine", engine)
    monkeypatch.setattr(
        dbbase, "SessionLocal", sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    )
    dbbase.Base.metadata.create_all(bind=engine)
    return dbbase
