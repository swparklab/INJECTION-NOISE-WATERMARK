"""High-level watermark service orchestrating embed/detect across the platform.

This is the façade used by the API layer. It ties together:
    - the payload/token codec (compact, ECC-protected delivery token),
    - the key provider (per-asset keyed marks),
    - the selected watermark engine (model selector),
    - the registry (records the delivery so a token resolves to a recipient),
    - the audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.core import registry as engine_registry
from app.core.detection_engine import DetectionEngine, TokenDetection
from app.payload.keystore import KeyProvider, get_key_provider
from app.payload.service import PayloadService, TokenCodec, WatermarkPayload


@dataclass
class EmbedOutcome:
    """Result of a high-level embed operation."""

    image: np.ndarray
    token_id: bytes
    model_id: str
    psnr: float
    ssim: float
    bits_embedded: int
    detail: dict = field(default_factory=dict)


class WatermarkService:
    """Façade for embedding and detecting watermarks with full provenance."""

    def __init__(
        self,
        key_provider: KeyProvider | None = None,
        token_codec: TokenCodec | None = None,
    ) -> None:
        self.key_provider = key_provider or get_key_provider()
        self.token_codec = token_codec or TokenCodec()
        self.payload_service = PayloadService(self.key_provider)
        self.detection = DetectionEngine(self.token_codec)

    def _key_for_asset(self, asset_id: str) -> bytes:
        """Derive the watermark spreading key for an asset."""
        return self.key_provider.derive(f"watermark:{asset_id}", length=32)

    # -- embed -------------------------------------------------------------
    def embed_image(
        self,
        image: np.ndarray,
        asset_id: str,
        model_id: str = "custom-noise",
        strength: float = 0.18,
        token_id: bytes | None = None,
    ) -> EmbedOutcome:
        """Embed a delivery token into an image with the selected engine.

        Args:
            image: RGB image.
            asset_id: Asset the token is scoped to (keys are asset-derived).
            model_id: Watermark model id (selector).
            strength: Embedding strength.
            token_id: Optional explicit token id (else random).

        Returns:
            EmbedOutcome with watermarked image and the token id to register.
        """
        engine = engine_registry.get_engine(model_id)
        token_id = token_id or self.token_codec.new_token_id()
        wire = self.token_codec.encode(token_id)
        key = self._key_for_asset(asset_id)
        res = engine.embed(image, wire, key, strength)
        return EmbedOutcome(
            image=res.image,
            token_id=token_id,
            model_id=model_id,
            psnr=res.psnr,
            ssim=res.ssim,
            bits_embedded=res.bits_embedded,
            detail=res.detail,
        )

    # -- detect ------------------------------------------------------------
    def detect_image(
        self,
        image: np.ndarray,
        asset_id: str,
        model_id: str = "custom-noise",
    ) -> TokenDetection:
        """Detect a watermark token in an image for a known asset + model."""
        key = self._key_for_asset(asset_id)
        return self.detection.detect_image(image, key, model_id)

    def detect_image_blind(
        self,
        image: np.ndarray,
        candidate_asset_ids: list[str],
        candidate_models: list[str] | None = None,
    ) -> tuple[str, TokenDetection] | None:
        """Detect across candidate assets + models (unknown-origin file).

        Returns:
            ``(asset_id, detection)`` for the first/strongest CRC-valid hit, or
            None if nothing detected.
        """
        best: tuple[str, TokenDetection] | None = None
        for asset_id in candidate_asset_ids:
            key = self._key_for_asset(asset_id)
            det = self.detection.detect_image_blind(image, key, candidate_models)
            if det.crc_ok:
                return asset_id, det
            if best is None or det.confidence > best[1].confidence:
                best = (asset_id, det)
        return best

    # -- video -------------------------------------------------------------
    def detect_video(
        self,
        frames: list[np.ndarray],
        asset_id: str,
        model_id: str = "custom-noise",
        vote_threshold: float = 0.5,
    ) -> TokenDetection:
        """Detect a watermark across video frames via majority vote."""
        key = self._key_for_asset(asset_id)
        return self.detection.detect_video_frames(frames, key, model_id, vote_threshold)
