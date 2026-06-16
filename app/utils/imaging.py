"""Image and bit-manipulation helpers shared across watermark engines."""

from __future__ import annotations

import cv2
import numpy as np


def bytes_to_bits(data: bytes) -> np.ndarray:
    """Convert bytes to a 1-D array of bits (MSB first), values in {0,1}."""
    arr = np.frombuffer(data, dtype=np.uint8)
    return np.unpackbits(arr).astype(np.int8)


def bits_to_bytes(bits: np.ndarray) -> bytes:
    """Convert a 1-D bit array (MSB first) back to bytes. Pads to byte boundary."""
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    pad = (-len(bits)) % 8
    if pad:
        bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
    return np.packbits(bits).tobytes()


def to_yuv(image: np.ndarray) -> np.ndarray:
    """Convert an RGB uint8 image to float32 YUV."""
    return cv2.cvtColor(image, cv2.COLOR_RGB2YUV).astype(np.float32)


def from_yuv(yuv: np.ndarray) -> np.ndarray:
    """Convert a float32 YUV image back to RGB uint8 (clipped)."""
    yuv = np.clip(yuv, 0, 255).astype(np.uint8)
    return cv2.cvtColor(yuv, cv2.COLOR_YUV2RGB)


def psnr(original: np.ndarray, modified: np.ndarray) -> float:
    """Peak signal-to-noise ratio in dB between two uint8 images."""
    a = original.astype(np.float64)
    b = modified.astype(np.float64)
    mse = np.mean((a - b) ** 2)
    if mse <= 1e-12:
        return 99.0
    return float(10.0 * np.log10((255.0**2) / mse))


def ssim(original: np.ndarray, modified: np.ndarray) -> float:
    """Mean structural similarity index between two images.

    Falls back gracefully if scikit-image is unavailable.
    """
    try:
        from skimage.metrics import structural_similarity as sk_ssim
    except Exception:  # pragma: no cover - optional dep
        return 0.0

    if original.ndim == 3:
        return float(
            sk_ssim(original, modified, channel_axis=2, data_range=255)
        )
    return float(sk_ssim(original, modified, data_range=255))


def block_view(channel: np.ndarray, block: int = 8) -> tuple[np.ndarray, int, int]:
    """Return non-overlapping ``block``x``block`` tiles of a 2-D channel.

    Returns:
        Tuple ``(blocks, n_rows, n_cols)`` where ``blocks`` has shape
        ``(n_rows*n_cols, block, block)``.
    """
    h, w = channel.shape
    n_rows, n_cols = h // block, w // block
    cropped = channel[: n_rows * block, : n_cols * block]
    tiles = (
        cropped.reshape(n_rows, block, n_cols, block)
        .transpose(0, 2, 1, 3)
        .reshape(-1, block, block)
    )
    return tiles, n_rows, n_cols


def unblock_view(tiles: np.ndarray, n_rows: int, n_cols: int, block: int = 8) -> np.ndarray:
    """Inverse of :func:`block_view`; reassemble tiles into a 2-D channel."""
    return (
        tiles.reshape(n_rows, n_cols, block, block)
        .transpose(0, 2, 1, 3)
        .reshape(n_rows * block, n_cols * block)
    )
