"""Diffusion-domain watermark adapters: Tree-Ring, Gaussian Shading, RingID.

These watermark the *initial latent noise* of a diffusion model, so the mark is
woven into AI-generated content itself (doc layer 3: Latent-domain Diffusion
Watermark). Full embedding requires a Stable Diffusion pipeline + GPU; the
``tree_ring`` adapter absorbs the project's original research implementation in
``src/tree_ring_watermark``.

For non-generative inputs (an already-rendered image) the adapters fall back to
the platform's robust image-domain engine so the model id remains usable in the
selector and detection flows.
"""

from __future__ import annotations

import logging

import numpy as np

from app.adapters.base import AdapterEngine
from app.core.base import DetectResult, EmbedResult

logger = logging.getLogger(__name__)


class TreeRingAdapter(AdapterEngine):
    """Tree-Ring watermark for diffusion-generated images.

    Native path wraps the original research code in ``src/tree_ring_watermark``
    (Fourier-space ring pattern injected into the initial latent). Requires a
    diffusion pipeline; see ``InjectionNoise.generate_watermarked`` for the
    latent-space flow. Falls back to the image-domain engine otherwise.
    """

    model_id = "tree-ring"
    media_types = ("image",)
    native_package = "tree_ring_watermark"

    def _load_native(self):
        # The research package provides the latent pattern + detection maths.
        # We expose it as available; actual generation needs a pipeline supplied
        # at call time (see app.core.latent_watermark), so image-domain embed
        # uses the fallback while the latent flow uses the native maths.
        import importlib

        return importlib.import_module("tree_ring_watermark")

    def _native_embed(self, image, payload, key, strength) -> EmbedResult:
        # Image-domain embedding for an already-generated frame uses the robust
        # internal engine; true latent embedding happens in the generation flow.
        res = self._fallback.embed(image, payload, key, strength)
        res.detail["note"] = "image-domain fallback; latent embed via generation flow"
        return res

    def _native_detect(self, image, key, payload_len) -> DetectResult:
        return self._fallback.detect(image, key, payload_len)


class GaussianShadingAdapter(AdapterEngine):
    """Gaussian Shading — performance-lossless diffusion watermark.

    Embeds the payload by *shaping* the sampled Gaussian latent so the generated
    distribution is statistically unchanged (no quality loss), recoverable by
    DDIM inversion. Native path requires a diffusion pipeline; falls back to the
    image-domain engine for already-rendered inputs.
    """

    model_id = "gaussian-shading"
    media_types = ("image",)
    native_package = "diffusers"

    def _load_native(self):
        import importlib

        return importlib.import_module("diffusers")

    def _native_embed(self, image, payload, key, strength) -> EmbedResult:
        res = self._fallback.embed(image, payload, key, strength)
        res.detail["note"] = "image-domain fallback; latent shading via generation flow"
        return res

    def _native_detect(self, image, key, payload_len) -> DetectResult:
        return self._fallback.detect(image, key, payload_len)


class RingIDAdapter(GaussianShadingAdapter):
    """RingID — multi-key ring identification extending Tree-Ring/Gaussian Shading."""

    model_id = "ringid"
    native_package = "tree_ring_watermark"
