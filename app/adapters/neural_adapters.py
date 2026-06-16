"""Neural watermark adapters: VideoSeal, Meta Seal, InvisMark, WAM.

These wrap external neural watermarking models. Each tries to import its native
backend; if unavailable it falls back to the platform's internal engine (see
:class:`~app.adapters.base.AdapterEngine`). The ``_load_native`` /
``_native_embed`` / ``_native_detect`` hooks are the production integration
points — fill them in when the corresponding model + weights are deployed.
"""

from __future__ import annotations

import numpy as np

from app.adapters.base import AdapterEngine
from app.core.base import DetectResult, EmbedResult


class VideoSealAdapter(AdapterEngine):
    """Meta VideoSeal — neural video watermarking (per-frame latent mark).

    Native backend: the ``videoseal`` package (https://github.com/facebookresearch/videoseal).
    Strong choice for general video; survives H.264/H.265 re-encoding.
    """

    model_id = "videoseal"
    media_types = ("video", "image")
    native_package = "videoseal"

    def _load_native(self):
        import importlib

        mod = importlib.import_module("videoseal")
        # videoseal.load("videoseal") returns an embedder/detector model.
        return mod.load("videoseal")  # pragma: no cover - requires weights

    def _native_embed(self, image, payload, key, strength) -> EmbedResult:  # pragma: no cover
        import torch

        from app.utils.imaging import bytes_to_bits, psnr, ssim

        bits = torch.tensor(bytes_to_bits(payload)[: self._native.nbits], dtype=torch.float32)
        frame = torch.from_numpy(image).permute(2, 0, 1).float() / 255.0
        out = self._native.embed(frame.unsqueeze(0), msgs=bits.unsqueeze(0), alpha=strength)
        wm = (out["imgs_w"][0].clamp(0, 1).permute(1, 2, 0).numpy() * 255).astype(np.uint8)
        return EmbedResult(wm, len(bits), psnr(image, wm), ssim(image, wm))

    def _native_detect(self, image, key, payload_len) -> DetectResult:  # pragma: no cover
        import torch

        from app.utils.imaging import bits_to_bytes

        frame = torch.from_numpy(image).permute(2, 0, 1).float().unsqueeze(0) / 255.0
        out = self._native.detect(frame)
        bits = (out["msgs"][0] > 0).to(torch.uint8).numpy()
        return DetectResult(True, float(out.get("score", 0.9)), bits, bits_to_bytes(bits))


class MetaSealAdapter(AdapterEngine):
    """Meta Seal / WAM-family image watermarking (general images & video frames)."""

    model_id = "metaseal"
    media_types = ("image", "video")
    native_package = "watermark_anything"

    def _load_native(self):
        import importlib

        return importlib.import_module(self.native_package)  # pragma: no cover


class InvisMarkAdapter(AdapterEngine):
    """InvisMark — high-capacity, high-fidelity invisible watermark for HD images.

    Native backend: the ``invismark`` package. Best for high-resolution stills
    where capacity and imperceptibility (very high PSNR) matter.
    """

    model_id = "invismark"
    media_types = ("image",)
    native_package = "invismark"

    def _load_native(self):
        import importlib

        return importlib.import_module(self.native_package)  # pragma: no cover


class WAMAdapter(AdapterEngine):
    """Watermark-Anything (WAM) — localized watermarking with segmentation.

    Native backend: the ``watermark_anything`` package. Supports detecting which
    *region* of an image carries the mark (partial / cropped detection).
    """

    model_id = "wam"
    media_types = ("image",)
    native_package = "watermark_anything"

    def _load_native(self):
        import importlib

        return importlib.import_module(self.native_package)  # pragma: no cover

    def detect(self, image, key, payload_len=None) -> DetectResult:
        """Detect and add a localization heat map (region-level watermark map)."""
        res = super().detect(image, key, payload_len)
        if res.localization is None and self._native is None:
            # Fallback localization: block-wise detection energy map.
            res.localization = self._fallback_localization(image, key)
        return res

    def _fallback_localization(self, image: np.ndarray, key: bytes) -> np.ndarray:
        """Coarse energy heat map by tiling the image and measuring response."""
        h, w = image.shape[:2]
        gh, gw = 8, 8
        heat = np.zeros((gh, gw), dtype=np.float32)
        th, tw = h // gh, w // gw
        for i in range(gh):
            for j in range(gw):
                tile = image[i * th : (i + 1) * th, j * tw : (j + 1) * tw]
                if tile.shape[0] < 16 or tile.shape[1] < 16:
                    continue
                d = self._fallback.detect(tile, key, payload_len=4)
                heat[i, j] = d.confidence
        return heat
