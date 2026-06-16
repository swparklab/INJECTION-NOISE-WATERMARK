"""Frequency-domain watermark engine.

Implements a robust blind watermark using **block DCT** with **spread-spectrum**
embedding in mid-frequency coefficients, **perceptual masking** to keep the mark
invisible, and a **keyed PN sequence** so only the holder of the secret key can
detect or decode the payload. Optionally combines a **DWT** decomposition so the
mark survives scaling and JPEG re-compression.

Algorithm (embed):
    1. Convert to YUV; operate on the luminance (Y) channel.
    2. (optional) DWT; embed in the LL/approximation sub-band for robustness.
    3. Split channel into 8x8 blocks; DCT each block.
    4. For each payload bit, modulate a keyed pseudo-random sign pattern over a
       set of mid-frequency coefficients (spread spectrum), scaled by a local
       perceptual mask (block texture/energy) and global ``strength``.
    5. Inverse DCT, (inverse DWT), back to RGB.

Detection is blind (original not required): regenerate the same keyed PN
pattern, correlate against the received mid-frequency coefficients per bit, and
threshold the correlation. Confidence is derived from correlation magnitude.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.core.base import DetectResult, EmbedResult, WatermarkEngine
from app.payload import crypto
from app.utils import imaging

# Mid-frequency coefficient positions in an 8x8 DCT block (zig-zag mid band).
_MID_BAND: list[tuple[int, int]] = [
    (1, 2), (2, 1), (2, 2), (1, 3), (3, 1), (2, 3), (3, 2), (4, 1),
    (1, 4), (3, 3), (4, 2), (2, 4), (5, 1), (1, 5), (4, 3), (3, 4),
]


class FrequencyWatermarkEngine(WatermarkEngine):
    """Block-DCT spread-spectrum watermark with perceptual masking."""

    model_id = "frequency"
    media_types = ("image",)

    def __init__(
        self,
        block: int = 8,
        use_dwt: bool = True,
        repeat: int = 5,
        coeffs_per_bit: int = 16,
    ) -> None:
        """Initialise the engine.

        Args:
            block: DCT block size (8 is JPEG-aligned and robust).
            use_dwt: Embed in the DWT approximation band for extra robustness.
            repeat: Repetition factor per bit (majority vote on detect).
            coeffs_per_bit: Number of mid-frequency coefficients spread per bit.
        """
        self.block = block
        self.use_dwt = use_dwt
        self.repeat = repeat
        self.coeffs_per_bit = min(coeffs_per_bit, len(_MID_BAND))

    # -- capacity ----------------------------------------------------------
    def _carrier_channel(self, y: np.ndarray) -> np.ndarray:
        if self.use_dwt:
            import pywt

            ll, _ = pywt.dwt2(y, "haar")
            return ll.astype(np.float32)
        return y

    def capacity_bits(self, image_shape: tuple[int, ...]) -> int:
        """Max payload bits for an image of the given shape."""
        h, w = image_shape[0], image_shape[1]
        if self.use_dwt:
            h, w = h // 2, w // 2
        n_blocks = (h // self.block) * (w // self.block)
        return max(0, n_blocks // self.repeat)

    # -- keyed pattern -----------------------------------------------------
    def _pn_signs(self, key: bytes, n_bits: int) -> np.ndarray:
        """Generate a keyed +/-1 PN matrix of shape (n_bits, coeffs_per_bit)."""
        need = n_bits * self.coeffs_per_bit
        stream = crypto.keystream(key, need)
        signs = np.frombuffer(stream, dtype=np.uint8).astype(np.int16)
        signs = np.where(signs & 1 == 1, 1, -1)
        return signs.reshape(n_bits, self.coeffs_per_bit)

    def _block_dct(self, tiles: np.ndarray) -> np.ndarray:
        return np.stack([cv2.dct(t) for t in tiles])

    def _block_idct(self, tiles: np.ndarray) -> np.ndarray:
        return np.stack([cv2.idct(t) for t in tiles])

    # -- embed -------------------------------------------------------------
    def embed(
        self,
        image: np.ndarray,
        payload: bytes,
        key: bytes,
        strength: float = 0.12,
    ) -> EmbedResult:
        """Embed payload bits into mid-frequency DCT coefficients."""
        yuv = imaging.to_yuv(image)
        y = yuv[:, :, 0].copy()
        carrier = self._carrier_channel(y)

        bits = imaging.bytes_to_bits(payload)
        n_bits = len(bits)
        cap = self.capacity_bits(image.shape)
        if n_bits > cap:
            raise ValueError(f"payload {n_bits} bits exceeds capacity {cap} bits")

        tiles, n_rows, n_cols = imaging.block_view(carrier, self.block)
        n_blocks = tiles.shape[0]
        dct_tiles = self._block_dct(tiles)

        signs = self._pn_signs(key, n_bits)
        positions = _MID_BAND[: self.coeffs_per_bit]

        # Each bit is written to `repeat` consecutive blocks (majority on detect).
        amplitude = strength * 12.0  # map [0,1]-ish strength to DCT units
        block_idx = 0
        for bi in range(n_bits):
            bit_val = 1 if bits[bi] else -1
            for _ in range(self.repeat):
                if block_idx >= n_blocks:
                    break
                tile = dct_tiles[block_idx]
                # Perceptual mask: scale by local AC energy (texture hides marks).
                ac_energy = float(np.sqrt(np.mean(tile[1:, 1:] ** 2)) + 1e-3)
                local_amp = amplitude * (0.5 + 0.5 * np.tanh(ac_energy / 8.0))
                for k, (r, c) in enumerate(positions):
                    tile[r, c] += bit_val * signs[bi, k] * local_amp
                block_idx += 1

        idct_tiles = self._block_idct(dct_tiles)
        carrier_wm = imaging.unblock_view(idct_tiles, n_rows, n_cols, self.block)

        if self.use_dwt:
            import pywt

            ll, (lh, hl, hh) = pywt.dwt2(y, "haar")
            ll[: carrier_wm.shape[0], : carrier_wm.shape[1]] = carrier_wm
            y_wm = pywt.idwt2((ll, (lh, hl, hh)), "haar")[: y.shape[0], : y.shape[1]]
        else:
            y_wm = np.zeros_like(y)
            y_wm[: carrier_wm.shape[0], : carrier_wm.shape[1]] = carrier_wm
            y_wm[carrier_wm.shape[0] :, :] = y[carrier_wm.shape[0] :, :]
            y_wm[:, carrier_wm.shape[1] :] = y[:, carrier_wm.shape[1] :]

        yuv[:, :, 0] = y_wm
        out = imaging.from_yuv(yuv)

        return EmbedResult(
            image=out,
            bits_embedded=n_bits,
            psnr=imaging.psnr(image, out),
            ssim=imaging.ssim(image, out),
            detail={"engine": self.model_id, "use_dwt": self.use_dwt, "repeat": self.repeat},
        )

    # -- detect ------------------------------------------------------------
    def detect(
        self,
        image: np.ndarray,
        key: bytes,
        payload_len: int | None = None,
    ) -> DetectResult:
        """Blind-detect payload by correlating keyed PN with DCT coefficients."""
        yuv = imaging.to_yuv(image)
        y = yuv[:, :, 0]
        carrier = self._carrier_channel(y)

        tiles, _, _ = imaging.block_view(carrier, self.block)
        n_blocks = tiles.shape[0]
        dct_tiles = self._block_dct(tiles)

        max_bits = (n_blocks // self.repeat)
        n_bits = (payload_len * 8) if payload_len else max_bits
        n_bits = min(n_bits, max_bits)

        signs = self._pn_signs(key, n_bits)
        positions = _MID_BAND[: self.coeffs_per_bit]

        # Estimate host noise scale at the carrier positions for a z-score.
        pos_arr = np.array(positions)
        host_samples = dct_tiles[:, pos_arr[:, 0], pos_arr[:, 1]].ravel()
        host_std = float(np.std(host_samples)) + 1e-9

        recovered = np.zeros(n_bits, dtype=np.uint8)
        zscores = np.zeros(n_bits, dtype=np.float64)
        block_idx = 0
        for bi in range(n_bits):
            responses = []
            for _ in range(self.repeat):
                if block_idx >= n_blocks:
                    break
                tile = dct_tiles[block_idx]
                acc = 0.0
                for k, (r, c) in enumerate(positions):
                    acc += signs[bi, k] * tile[r, c]
                responses.append(acc)
                block_idx += 1
            if not responses:
                break
            total = float(np.sum(responses))
            # null std for sum of repeat*coeffs keyed terms
            null_std = host_std * np.sqrt(self.coeffs_per_bit * len(responses))
            zscores[bi] = total / null_std
            recovered[bi] = 1 if total > 0 else 0

        mean_abs_z = float(np.mean(np.abs(zscores))) if n_bits else 0.0
        confidence = float(np.tanh(max(0.0, mean_abs_z - 0.8) / 3.0))
        detected = confidence > 0.2

        return DetectResult(
            detected=detected,
            confidence=confidence,
            payload_bits=recovered,
            payload_bytes=imaging.bits_to_bytes(recovered),
            detail={"engine": self.model_id, "n_bits": int(n_bits), "mean_abs_z": mean_abs_z},
        )
