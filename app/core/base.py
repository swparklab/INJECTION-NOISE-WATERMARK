"""Core watermark engine interfaces and shared data types.

Every watermark engine (frequency, keyed-gaussian, latent, neural, …) and every
external adapter (VideoSeal, InvisMark, …) implements :class:`WatermarkEngine`
so the platform can treat them uniformly via the model selector.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class EmbedResult:
    """Result of embedding a watermark into an image.

    Attributes:
        image: Watermarked image (H, W, C) uint8.
        bits_embedded: Number of payload bits actually embedded.
        psnr: Peak signal-to-noise ratio vs. the original (image quality).
        ssim: Structural similarity vs. the original.
        detail: Engine-specific metadata.
    """

    image: np.ndarray
    bits_embedded: int
    psnr: float = 0.0
    ssim: float = 0.0
    detail: dict = field(default_factory=dict)


@dataclass
class DetectResult:
    """Result of detecting / extracting a watermark from an image.

    Attributes:
        detected: Whether a watermark was detected.
        confidence: Detection confidence in [0, 1].
        payload_bits: Recovered raw bits (may be noisy; ECC applied downstream).
        payload_bytes: Recovered bytes if the engine packs to bytes.
        bit_error_rate: Estimated BER where measurable.
        localization: Optional (H, W) heat map of watermark energy.
        detail: Engine-specific metadata.
    """

    detected: bool
    confidence: float
    payload_bits: np.ndarray | None = None
    payload_bytes: bytes | None = None
    bit_error_rate: float | None = None
    localization: np.ndarray | None = None
    detail: dict = field(default_factory=dict)


class WatermarkEngine(ABC):
    """Abstract watermark engine."""

    #: Stable identifier used by the model selector / registry.
    model_id: str = "base"
    #: Media types supported, e.g. ``("image",)`` or ``("image", "video")``.
    media_types: tuple[str, ...] = ("image",)

    @abstractmethod
    def capacity_bits(self, image_shape: tuple[int, ...]) -> int:
        """Return the payload capacity in bits for the given image shape."""

    @abstractmethod
    def embed(
        self,
        image: np.ndarray,
        payload: bytes,
        key: bytes,
        strength: float = 0.12,
    ) -> EmbedResult:
        """Embed ``payload`` into ``image`` using secret ``key``.

        Args:
            image: RGB image (H, W, 3) uint8.
            payload: Opaque payload bytes (already ECC/crypto framed).
            key: Secret key controlling the watermark spreading sequence.
            strength: Embedding strength (perceptibility/robustness trade-off).
        """

    @abstractmethod
    def detect(
        self,
        image: np.ndarray,
        key: bytes,
        payload_len: int | None = None,
    ) -> DetectResult:
        """Detect/extract a watermark from ``image`` using secret ``key``.

        Args:
            image: RGB image (H, W, 3) uint8.
            key: Secret key used at embed time.
            payload_len: Expected payload length in bytes, if known.
        """
