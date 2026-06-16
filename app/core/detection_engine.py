"""Unified detection engine.

Coordinates blind detection across one or more watermark engines, recovers the
compact token via ECC, and exposes image / video (frame-vote) detection with
confidence scoring and localization. This is the engine behind the
``/detect`` and ``/trace`` APIs.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from app.core import registry as engine_registry
from app.core.base import DetectResult
from app.payload.service import TokenCodec
from app.utils import imaging


@dataclass
class TokenDetection:
    """Outcome of attempting to recover a delivery token from media."""

    model_id: str
    detected: bool
    confidence: float
    token_id: bytes | None
    crc_ok: bool
    detail: dict = field(default_factory=dict)


class DetectionEngine:
    """High-level detector across registered watermark engines."""

    def __init__(self, token_codec: TokenCodec | None = None) -> None:
        self.token_codec = token_codec or TokenCodec()

    # -- single image ------------------------------------------------------
    def detect_image(
        self,
        image: np.ndarray,
        key: bytes,
        model_id: str,
    ) -> TokenDetection:
        """Detect a watermark in a single image with a known model + key."""
        engine = engine_registry.get_engine(model_id)
        wire_len = self.token_codec.wire_len()
        res: DetectResult = engine.detect(image, key, payload_len=wire_len)
        token_id, crc_ok = (None, False)
        if res.payload_bytes:
            token_id, crc_ok = self.token_codec.decode(res.payload_bytes[:wire_len])
        # CRC success is strong evidence even if raw confidence is modest.
        confidence = max(res.confidence, 0.9 if crc_ok else 0.0)
        return TokenDetection(
            model_id=model_id,
            detected=bool(res.detected or crc_ok),
            confidence=confidence,
            token_id=token_id if crc_ok else (token_id if res.detected else None),
            crc_ok=crc_ok,
            detail={"raw_confidence": res.confidence, **res.detail},
        )

    def detect_image_blind(
        self,
        image: np.ndarray,
        key: bytes,
        candidate_models: list[str] | None = None,
    ) -> TokenDetection:
        """Try multiple models and return the strongest detection.

        Used when the embedding model is unknown (a leaked file in the wild).
        """
        models = candidate_models or engine_registry.available_models()
        best: TokenDetection | None = None
        for model_id in models:
            try:
                det = self.detect_image(image, key, model_id)
            except Exception:  # noqa: BLE001 - skip engines that can't run
                continue
            if best is None or det.confidence > best.confidence:
                best = det
            if det.crc_ok:  # exact token recovery — stop early
                return det
        return best or TokenDetection("none", False, 0.0, None, False)

    # -- video (frame voting) ---------------------------------------------
    def detect_video_frames(
        self,
        frames: list[np.ndarray],
        key: bytes,
        model_id: str,
        vote_threshold: float = 0.5,
    ) -> TokenDetection:
        """Detect across video frames using majority vote on recovered tokens.

        Each frame is detected independently; the most common CRC-valid token id
        wins (doc requirement: Frame Vote survival). This is robust to per-frame
        re-encoding noise and partial occlusion.

        Args:
            frames: List of RGB frames.
            key: Secret key.
            model_id: Watermark model used at embed time.
            vote_threshold: Fraction of valid frames required to accept a token.

        Returns:
            Aggregated TokenDetection.
        """
        votes: Counter[bytes] = Counter()
        confidences: list[float] = []
        valid = 0
        for frame in frames:
            det = self.detect_image(frame, key, model_id)
            confidences.append(det.confidence)
            if det.crc_ok and det.token_id:
                votes[det.token_id] += 1
                valid += 1

        if not votes:
            return TokenDetection(
                model_id=model_id,
                detected=False,
                confidence=float(np.mean(confidences)) if confidences else 0.0,
                token_id=None,
                crc_ok=False,
                detail={"frames": len(frames), "valid_frames": 0},
            )

        token_id, count = votes.most_common(1)[0]
        vote_ratio = count / max(len(frames), 1)
        detected = vote_ratio >= vote_threshold or count >= 3
        return TokenDetection(
            model_id=model_id,
            detected=detected,
            confidence=float(min(1.0, vote_ratio + 0.3)),
            token_id=token_id,
            crc_ok=True,
            detail={
                "frames": len(frames),
                "valid_frames": valid,
                "vote_ratio": vote_ratio,
                "vote_count": count,
            },
        )

    # -- localization ------------------------------------------------------
    def localize(self, image: np.ndarray, key: bytes, model_id: str) -> np.ndarray | None:
        """Return a coarse heat map of watermark energy if the engine supports it."""
        engine = engine_registry.get_engine(model_id)
        res = engine.detect(image, key, payload_len=self.token_codec.wire_len())
        return res.localization
