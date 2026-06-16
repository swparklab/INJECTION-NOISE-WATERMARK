"""Adapter base classes for external / neural watermark backends.

Each adapter conforms to :class:`~app.core.base.WatermarkEngine` so external
models (VideoSeal, Meta Seal, InvisMark, WAM) plug into the same selector,
detection and tracking flows as the built-in engines.

Because proprietary neural model weights cannot be bundled, every adapter:
    1. Attempts to load its **native backend** if the optional package + weights
       are present (the real production path), and
    2. Otherwise transparently falls back to the platform's robust internal
       spread-spectrum engine so the system is fully operational end-to-end,
       clearly flagging ``backend="fallback"`` in result metadata and logs.

This makes the platform runnable out-of-the-box while keeping each native
integration a drop-in (implement :meth:`_load_native`).
"""

from __future__ import annotations

import logging

import numpy as np

from app.core.base import DetectResult, EmbedResult, WatermarkEngine
from app.core.keyed_gaussian import KeyedGaussianEngine

logger = logging.getLogger(__name__)


class AdapterEngine(WatermarkEngine):
    """Base adapter that prefers a native backend, falling back internally."""

    model_id = "adapter"
    media_types = ("image",)
    native_package: str | None = None

    def __init__(self) -> None:
        self._native = None
        self._fallback = KeyedGaussianEngine()
        try:
            self._native = self._load_native()
            if self._native is not None:
                logger.info("Adapter %s using native backend", self.model_id)
        except Exception as exc:  # noqa: BLE001 - optional backend
            logger.warning(
                "Adapter %s native backend unavailable (%s); using fallback engine",
                self.model_id,
                exc,
            )
            self._native = None

    # -- override in subclasses -------------------------------------------
    def _load_native(self):  # noqa: ANN202 - backend-specific object
        """Load and return the native backend object, or None if unavailable."""
        return None

    def _native_embed(
        self, image: np.ndarray, payload: bytes, key: bytes, strength: float
    ) -> EmbedResult:  # pragma: no cover - requires native backend
        raise NotImplementedError

    def _native_detect(
        self, image: np.ndarray, key: bytes, payload_len: int | None
    ) -> DetectResult:  # pragma: no cover - requires native backend
        raise NotImplementedError

    # -- uniform interface -------------------------------------------------
    @property
    def backend(self) -> str:
        """Return ``"native"`` or ``"fallback"`` describing the active backend."""
        return "native" if self._native is not None else "fallback"

    def capacity_bits(self, image_shape: tuple[int, ...]) -> int:
        return self._fallback.capacity_bits(image_shape)

    def embed(
        self, image: np.ndarray, payload: bytes, key: bytes, strength: float = 0.12
    ) -> EmbedResult:
        if self._native is not None:
            res = self._native_embed(image, payload, key, strength)
        else:
            res = self._fallback.embed(image, payload, key, strength)
        res.detail.update({"adapter": self.model_id, "backend": self.backend})
        return res

    def detect(
        self, image: np.ndarray, key: bytes, payload_len: int | None = None
    ) -> DetectResult:
        if self._native is not None:
            res = self._native_detect(image, key, payload_len)
        else:
            res = self._fallback.detect(image, key, payload_len)
        res.detail.update({"adapter": self.model_id, "backend": self.backend})
        return res
