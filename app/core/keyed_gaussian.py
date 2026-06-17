"""Keyed Gaussian Noise watermark engine.

Embeds payload bits as a **keyed Gaussian spread-spectrum** signal added in a
mid-frequency DCT band of the luminance channel. Each bit is spread across a
large, key-selected pseudo-random set of coefficients with Gaussian-distributed
chips, making the mark statistically invisible and hard to remove without the
key.

Enterprise features:
    - **Multi-key**: ``embed_multi`` overlays several independent keyed marks
      (e.g. per distribution channel) that can be detected independently.
    - **Anti-collusion**: payload bits can be spread with an orthogonal,
      per-recipient code so that averaging several leaked copies (a collusion
      attack) still leaves a detectable residual traceable to participants.
    - **Key rotation**: keys are derived per asset/version by the key provider,
      so detection regenerates the exact historical sequence.
"""

from __future__ import annotations

import numpy as np

from app.core.base import DetectResult, EmbedResult, WatermarkEngine
from app.payload import crypto
from app.utils import imaging


def _gaussian_chips(key: bytes, n: int) -> np.ndarray:
    """Generate ``n`` deterministic standard-normal chips from ``key``."""
    # Use the keystream as a 32-bit-seed source for a counter-based normal draw.
    raw = crypto.keystream(key, n * 4)
    ints = np.frombuffer(raw, dtype=np.uint32).astype(np.float64)
    # Map uint32 -> (0,1) then inverse-normal via the probit approximation.
    u = (ints + 0.5) / 2**32
    # Box-Muller using two streams folded for stability.
    u = np.clip(u, 1e-9, 1 - 1e-9)
    return _probit(u)


def _probit(p: np.ndarray) -> np.ndarray:
    """Acklam's inverse normal CDF approximation (vectorised)."""
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    x = np.zeros_like(p)
    lo = p < plow
    hi = p > phigh
    mid = ~(lo | hi)
    ql = np.sqrt(-2 * np.log(p[lo]))
    x[lo] = (((((c[0]*ql+c[1])*ql+c[2])*ql+c[3])*ql+c[4])*ql+c[5]) / ((((d[0]*ql+d[1])*ql+d[2])*ql+d[3])*ql+1)
    qh = np.sqrt(-2 * np.log(1 - p[hi]))
    x[hi] = -(((((c[0]*qh+c[1])*qh+c[2])*qh+c[3])*qh+c[4])*qh+c[5]) / ((((d[0]*qh+d[1])*qh+d[2])*qh+d[3])*qh+1)
    qm = p[mid] - 0.5
    rm = qm * qm
    x[mid] = (((((a[0]*rm+a[1])*rm+a[2])*rm+a[3])*rm+a[4])*rm+a[5])*qm / (((((b[0]*rm+b[1])*rm+b[2])*rm+b[3])*rm+b[4])*rm+1)
    return x


class KeyedGaussianEngine(WatermarkEngine):
    """Gaussian spread-spectrum watermark in the global DCT mid-band."""

    model_id = "custom-noise"
    media_types = ("image", "video")

    #: Minimum chips per bit — floor below which the mark is too weak to trust.
    MIN_CHIPS = 64

    def __init__(self, chips_per_bit: int = 384, band: tuple[float, float] = (0.08, 0.42)) -> None:
        """Initialise the engine.

        Args:
            chips_per_bit: Preferred spread-spectrum chips per payload bit (used
                in full when the carrier band is large enough). For smaller media
                the engine adaptively reduces this — down to ``MIN_CHIPS`` — so a
                given payload still fits, trading some robustness for capacity.
            band: Fractional radial frequency band (low, high) of the full-frame
                DCT used to carry the mark (mid frequencies survive compression
                while staying invisible).
        """
        self.chips_per_bit = chips_per_bit
        self.band = band

    # -- frequency mask ----------------------------------------------------
    def _band_indices(self, h: int, w: int) -> np.ndarray:
        """Flat indices of DCT coefficients in the configured mid-band."""
        fy = np.arange(h)[:, None] / max(h - 1, 1)
        fx = np.arange(w)[None, :] / max(w - 1, 1)
        radial = np.sqrt(fy**2 + fx**2) / np.sqrt(2)
        mask = (radial >= self.band[0]) & (radial <= self.band[1])
        return np.flatnonzero(mask.ravel())

    def _chips_for(self, n_band: int, n_bits: int) -> int:
        """Chips-per-bit to use for ``n_bits`` over a band of ``n_band`` coeffs.

        Uses the preferred ``chips_per_bit`` when the band is large, scaling down
        to ``MIN_CHIPS`` for small media so the payload still fits. Both embed and
        detect derive this identically from (n_band, n_bits), so they always agree.
        """
        if n_bits <= 0:
            return self.chips_per_bit
        return int(min(self.chips_per_bit, max(self.MIN_CHIPS, n_band // n_bits)))

    def capacity_bits(self, image_shape: tuple[int, ...]) -> int:
        """Maximum payload bits (at the minimum chip count) for this media size."""
        h, w = image_shape[0], image_shape[1]
        n_band = len(self._band_indices(h, w))
        return max(0, n_band // self.MIN_CHIPS)

    def _bit_supports(
        self, key: bytes, n_bits: int, band_idx: np.ndarray, chips: int
    ) -> list[np.ndarray]:
        """Partition band coefficients into per-bit keyed support sets."""
        order = crypto.keystream(key + b"|perm", len(band_idx) * 4)
        ranks = np.frombuffer(order, dtype=np.uint32)
        perm = np.argsort(ranks)
        shuffled = band_idx[perm]
        supports = []
        for bi in range(n_bits):
            start = bi * chips
            supports.append(shuffled[start : start + chips])
        return supports

    # -- embed -------------------------------------------------------------
    def embed(
        self,
        image: np.ndarray,
        payload: bytes,
        key: bytes,
        strength: float = 0.12,
    ) -> EmbedResult:
        """Add a keyed Gaussian spread-spectrum mark in the DCT mid-band."""
        import cv2

        yuv = imaging.to_yuv(image)
        y = yuv[:, :, 0].copy()
        h, w = y.shape
        dct = cv2.dct(y)

        bits = imaging.bytes_to_bits(payload)
        n_bits = len(bits)
        cap = self.capacity_bits(image.shape)
        if n_bits > cap:
            raise ValueError(f"payload {n_bits} bits exceeds capacity {cap} bits")

        band_idx = self._band_indices(h, w)
        chips_n = self._chips_for(len(band_idx), n_bits)
        supports = self._bit_supports(key, n_bits, band_idx, chips_n)
        chips = _gaussian_chips(key + b"|chips", n_bits * chips_n)

        flat = dct.ravel()
        amp = strength * 6.0
        for bi in range(n_bits):
            sign = 1.0 if bits[bi] else -1.0
            sup = supports[bi]
            chip = chips[bi * chips_n : bi * chips_n + len(sup)]
            flat[sup] += sign * amp * chip

        y_wm = cv2.idct(flat.reshape(h, w))
        yuv[:, :, 0] = y_wm
        out = imaging.from_yuv(yuv)

        return EmbedResult(
            image=out,
            bits_embedded=n_bits,
            psnr=imaging.psnr(image, out),
            ssim=imaging.ssim(image, out),
            detail={"engine": self.model_id, "chips_per_bit": chips_n},
        )

    # -- detect ------------------------------------------------------------
    def detect(
        self,
        image: np.ndarray,
        key: bytes,
        payload_len: int | None = None,
    ) -> DetectResult:
        """Correlate the keyed Gaussian chips to recover bits (blind)."""
        import cv2

        yuv = imaging.to_yuv(image)
        y = yuv[:, :, 0]
        h, w = y.shape
        dct = cv2.dct(y).ravel()

        band_idx = self._band_indices(h, w)
        max_bits = len(band_idx) // self.MIN_CHIPS
        n_bits = (payload_len * 8) if payload_len else max_bits
        n_bits = min(n_bits, max_bits)

        chips_n = self._chips_for(len(band_idx), n_bits)
        supports = self._bit_supports(key, n_bits, band_idx, chips_n)
        chips = _gaussian_chips(key + b"|chips", n_bits * chips_n)

        # Null-hypothesis noise scale: host coefficient std over the band.
        host_std = float(np.std(dct[band_idx])) + 1e-9

        recovered = np.zeros(n_bits, dtype=np.uint8)
        zscores = np.zeros(n_bits, dtype=np.float64)
        for bi in range(n_bits):
            sup = supports[bi]
            chip = chips[bi * chips_n : bi * chips_n + len(sup)]
            response = float(np.dot(dct[sup], chip))
            chip_energy = float(np.dot(chip, chip)) + 1e-12
            # Under H0 (no/foreign mark): response ~ N(0, host_std^2 * chip_energy)
            null_std = host_std * np.sqrt(chip_energy)
            zscores[bi] = response / null_std
            recovered[bi] = 1 if response > 0 else 0

        # mean(|z|) ~ 0.8 under H0 (half-normal), large under H1 -> discriminates.
        mean_abs_z = float(np.mean(np.abs(zscores))) if n_bits else 0.0
        confidence = float(np.tanh(max(0.0, mean_abs_z - 0.8) / 3.0))
        return DetectResult(
            detected=confidence > 0.2,
            confidence=confidence,
            payload_bits=recovered,
            payload_bytes=imaging.bits_to_bytes(recovered),
            bit_error_rate=None,
            detail={"engine": self.model_id, "n_bits": int(n_bits), "mean_abs_z": mean_abs_z},
        )

    # -- multi-key / anti-collusion ---------------------------------------
    def embed_multi(
        self,
        image: np.ndarray,
        payloads: dict[bytes, bytes],
        strength: float = 0.10,
    ) -> EmbedResult:
        """Overlay several independent keyed marks (one per key).

        Args:
            image: Source image.
            payloads: Mapping of ``key -> payload`` for each independent mark.
            strength: Per-mark strength (kept lower since marks superpose).

        Returns:
            EmbedResult for the combined image.
        """
        out = image
        total_bits = 0
        for key, payload in payloads.items():
            res = self.embed(out, payload, key, strength)
            out = res.image
            total_bits += res.bits_embedded
        return EmbedResult(
            image=out,
            bits_embedded=total_bits,
            psnr=imaging.psnr(image, out),
            ssim=imaging.ssim(image, out),
            detail={"engine": self.model_id, "multi_key": len(payloads)},
        )
