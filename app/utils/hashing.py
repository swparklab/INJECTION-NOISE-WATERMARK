"""Content and perceptual hashing utilities.

- ``content_hash``: cryptographic SHA-256 over raw bytes (exact-match identity).
- ``perceptual_hash``: DCT-based pHash robust to compression/resize, used to
  match re-encoded copies back to a registered original.
"""

from __future__ import annotations

import hashlib

import cv2
import numpy as np


def content_hash(data: bytes) -> str:
    """Return SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def perceptual_hash(image: np.ndarray, hash_size: int = 16) -> str:
    """Compute a DCT-based perceptual hash (pHash) of an image.

    Args:
        image: Image as an ``np.ndarray`` (H, W) or (H, W, C), any dtype.
        hash_size: Size of the low-frequency DCT block kept (hash bits =
            ``hash_size**2``).

    Returns:
        Hex string of the perceptual hash.
    """
    if image.ndim == 3:
        image = cv2.cvtColor(image.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    img = cv2.resize(image.astype(np.float32), (hash_size * 4, hash_size * 4))
    dct = cv2.dct(img)
    low = dct[:hash_size, :hash_size]
    med = np.median(low[1:, 1:])  # exclude DC term from threshold
    bits = (low > med).flatten()
    # pack bits to hex
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    nbytes = (len(bits) + 7) // 8
    return value.to_bytes(nbytes, "big").hex()


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """Hamming distance between two equal-length hex hashes (bit differences)."""
    a = int(hash_a, 16)
    b = int(hash_b, 16)
    return bin(a ^ b).count("1")


def perceptual_similarity(hash_a: str, hash_b: str) -> float:
    """Return similarity in [0, 1] between two perceptual hashes."""
    if len(hash_a) != len(hash_b):
        return 0.0
    total_bits = len(hash_a) * 4
    if total_bits == 0:
        return 0.0
    return 1.0 - hamming_distance(hash_a, hash_b) / total_bits
