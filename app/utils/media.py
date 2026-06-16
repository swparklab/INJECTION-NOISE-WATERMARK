"""Helpers to decode/encode image bytes for the API layer."""

from __future__ import annotations

import cv2
import numpy as np


def decode_image(data: bytes) -> np.ndarray:
    """Decode image bytes to an RGB uint8 ndarray."""
    arr = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("could not decode image bytes")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def encode_image(image: np.ndarray, fmt: str = ".png") -> bytes:
    """Encode an RGB uint8 ndarray to bytes (PNG by default, lossless)."""
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    ok, enc = cv2.imencode(fmt, bgr)
    if not ok:
        raise ValueError("could not encode image")
    return enc.tobytes()
