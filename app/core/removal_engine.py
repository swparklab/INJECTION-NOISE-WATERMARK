"""Watermark removal engine (rights-holder / verifier use only).

Implements the removal methods from the development document section 7.6. This
capability is intended for the rights holder or an independent verifier to
demonstrate watermark fragility / perform forensic separation — every removal
is audit-logged.

Methods:
    - ``frequency_suppression``: attenuate energy in the watermark's frequency
      band (blind; no key needed).
    - ``neural_denoising``: edge-preserving denoise that strips low-amplitude
      additive marks (blind).
    - ``template_cancellation``: if the secret key is known, regenerate the exact
      keyed pattern and subtract it (keyed; highest quality / success).
    - ``residual_reconstruction``: estimate the watermark residual via a smoothed
      reference and reconstruct the host.
    - ``watermark_isolation``: separate and return the isolated watermark noise
      (for forensic analysis / "noise separation" viewing).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.core import registry as engine_registry
from app.utils import imaging


@dataclass
class RemovalResult:
    """Result of a removal operation."""

    image: np.ndarray
    method: str
    watermark_detected_before: bool
    watermark_detected_after: bool
    removal_success: float
    quality_score: float
    isolated_watermark: np.ndarray | None = None
    detail: dict = field(default_factory=dict)


class RemovalEngine:
    """Removal / forensic-separation operations on watermarked media."""

    # -- blind methods -----------------------------------------------------
    def frequency_suppression(self, image: np.ndarray, band=(0.08, 0.45), attenuation=0.5) -> np.ndarray:
        """Attenuate the mid-frequency DCT band that typically carries the mark."""
        yuv = imaging.to_yuv(image)
        y = yuv[:, :, 0]
        h, w = y.shape
        dct = cv2.dct(y)
        fy = np.arange(h)[:, None] / max(h - 1, 1)
        fx = np.arange(w)[None, :] / max(w - 1, 1)
        radial = np.sqrt(fy**2 + fx**2) / np.sqrt(2)
        mask = (radial >= band[0]) & (radial <= band[1])
        dct[mask] *= attenuation
        yuv[:, :, 0] = cv2.idct(dct)
        return imaging.from_yuv(yuv)

    def neural_denoising(self, image: np.ndarray, strength: int = 7) -> np.ndarray:
        """Edge-preserving denoise (Non-Local Means) to strip additive marks."""
        return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)

    # -- keyed method ------------------------------------------------------
    def template_cancellation(
        self, image: np.ndarray, key: bytes, model_id: str, wire_len: int, strength: float = 0.18
    ) -> np.ndarray:
        """Subtract the exact keyed watermark pattern (requires the secret key).

        Re-detects the bits, regenerates the corresponding embedding signal, and
        subtracts it — the cleanest removal when the holder possesses the key.
        """
        engine = engine_registry.get_engine(model_id)
        det = engine.detect(image, key, payload_len=wire_len)
        if det.payload_bytes is None:
            return image
        # Re-embed the detected pattern with negative strength to cancel it.
        cancel = engine.embed(image, det.payload_bytes[:wire_len], key, -strength)
        return cancel.image

    # -- residual / isolation ---------------------------------------------
    def residual_reconstruction(self, image: np.ndarray, sigma: float = 1.2) -> np.ndarray:
        """Reconstruct the host by replacing high-freq residual with a smooth est."""
        smooth = cv2.GaussianBlur(image, (0, 0), sigma)
        # keep most of the smooth base, drop a fraction of the residual (the mark)
        residual = image.astype(np.float32) - smooth.astype(np.float32)
        recon = smooth.astype(np.float32) + residual * 0.35
        return np.clip(recon, 0, 255).astype(np.uint8)

    def watermark_isolation(self, image: np.ndarray, sigma: float = 1.0) -> np.ndarray:
        """Isolate the watermark noise layer for forensic "noise separation" view.

        Returns a normalised visualisation of the high-frequency residual where
        the (otherwise invisible) injected noise becomes visible — the inverse of
        the platform's core thesis ("noise separation to view the mark").
        """
        smooth = cv2.GaussianBlur(image, (0, 0), sigma).astype(np.float32)
        residual = image.astype(np.float32) - smooth
        # normalise residual to a viewable range
        r = residual - residual.min()
        denom = (residual.max() - residual.min()) or 1.0
        return (r / denom * 255).astype(np.uint8)

    # -- orchestration -----------------------------------------------------
    def remove(
        self,
        image: np.ndarray,
        method: str = "frequency_suppression",
        key: bytes | None = None,
        model_id: str = "custom-noise",
        wire_len: int = 18,
    ) -> RemovalResult:
        """Run a removal method and measure success + quality.

        Args:
            image: Watermarked RGB image.
            method: One of the removal method names.
            key: Secret key (required for ``template_cancellation``).
            model_id: Model id for detection / template cancellation.
            wire_len: Token wire length for detection.

        Returns:
            RemovalResult with cleaned image, success and quality metrics.
        """
        # Measure detectability before (needs key to be meaningful).
        before = self._detectable(image, key, model_id, wire_len)
        isolated = None

        if method == "frequency_suppression":
            out = self.frequency_suppression(image)
        elif method == "neural_denoising":
            out = self.neural_denoising(image)
        elif method == "template_cancellation":
            if key is None:
                raise ValueError("template_cancellation requires the secret key")
            out = self.template_cancellation(image, key, model_id, wire_len)
        elif method == "residual_reconstruction":
            out = self.residual_reconstruction(image)
        elif method == "watermark_isolation":
            isolated = self.watermark_isolation(image)
            out = self.frequency_suppression(image)  # also suppress in the returned host
        else:
            raise ValueError(f"Unknown removal method: {method}")

        after = self._detectable(out, key, model_id, wire_len)
        # success: dropped detectability; quality: SSIM vs the (watermarked) input
        removal_success = 1.0 if (before and not after) else (0.5 if before else 0.0)
        if before:
            removal_success = max(0.0, before_conf := (before[1] - after[1]) / max(before[1], 1e-6))
            removal_success = float(np.clip(before_conf, 0.0, 1.0))
        quality = imaging.ssim(image, out)

        return RemovalResult(
            image=out,
            method=method,
            watermark_detected_before=bool(before and before[0]),
            watermark_detected_after=bool(after and after[0]),
            removal_success=round(removal_success, 4),
            quality_score=round(quality, 4),
            isolated_watermark=isolated,
            detail={"model": model_id},
        )

    def _detectable(self, image, key, model_id, wire_len) -> tuple[bool, float] | None:
        if key is None:
            return None
        engine = engine_registry.get_engine(model_id)
        d = engine.detect(image, key, payload_len=wire_len)
        return d.detected, d.confidence
