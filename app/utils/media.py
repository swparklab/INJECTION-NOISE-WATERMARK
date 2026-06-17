"""Helpers to decode/encode image bytes for the API layer."""

from __future__ import annotations

import io

import cv2
import numpy as np

# Opportunistically enable HEIC/HEIF (iPhone) support if pillow-heif is present.
try:  # pragma: no cover - optional dependency
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # noqa: BLE001
    pass


def decode_image(data: bytes) -> np.ndarray:
    """Decode image bytes to an RGB uint8 ndarray.

    Tries OpenCV first (fast, common formats), then falls back to Pillow which
    handles more formats and edge cases (WebP, GIF, paletted/RGBA/16-bit PNG,
    CMYK JPEG, and HEIC when ``pillow-heif`` is installed).

    Raises:
        ValueError: If the bytes are empty or not a decodable image (e.g. a
            video file was uploaded to an image endpoint).
    """
    if not data:
        raise ValueError("empty file upload")

    arr = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is not None:
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # Fallback: Pillow supports formats / quirks OpenCV rejects.
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        img.load()
        return np.array(img.convert("RGB"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "could not decode image — unsupported or corrupt image format "
            "(if this is a video, use the Video media type)"
        ) from exc


def encode_image(image: np.ndarray, fmt: str = ".png") -> bytes:
    """Encode an RGB uint8 ndarray to bytes (PNG by default, lossless)."""
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    ok, enc = cv2.imencode(fmt, bgr)
    if not ok:
        raise ValueError("could not encode image")
    return enc.tobytes()
