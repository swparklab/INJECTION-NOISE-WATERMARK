"""Model selector endpoints: list available watermark models."""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException

from app.core import registry as engine_registry
from app.schemas.api import ModelInfo, ModelsResponse

router = APIRouter(tags=["models"])

_DESCRIPTIONS: dict[str, tuple[str, list[str], str]] = {
    "custom-noise": ("Custom Noise Engine", ["image", "video"], "Keyed Gaussian spread-spectrum"),
    "frequency": ("Frequency Watermark", ["image"], "Block-DCT + DWT spread spectrum"),
    "videoseal": ("VideoSeal", ["video", "image"], "Neural video watermark"),
    "metaseal": ("Meta Seal", ["image", "video"], "Neural image/video watermark"),
    "invismark": ("InvisMark", ["image"], "High-resolution invisible watermark"),
    "wam": ("Watermark Anything", ["image"], "Localized / partial detection"),
    "tree-ring": ("Tree-Ring", ["image"], "Diffusion latent Fourier watermark"),
    "gaussian-shading": ("Gaussian Shading", ["image"], "Performance-lossless diffusion watermark"),
    "ringid": ("RingID", ["image"], "Multi-key ring identification"),
}


@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """List all registered watermark models and their capabilities."""
    ids = engine_registry.available_models()
    details = []
    for mid in ids:
        name, media_types, desc = _DESCRIPTIONS.get(mid, (mid, ["image"], ""))
        details.append(ModelInfo(id=mid, name=name, media_types=media_types, description=desc))
    return ModelsResponse(models=ids, details=details)


@router.post("/watermark/models", response_model=ModelsResponse)
async def list_models_post() -> ModelsResponse:
    """POST alias for model listing (per API spec section 8)."""
    return await list_models()


@router.get("/capacity")
async def capacity(model: str = "custom-noise", width: int = 512, height: int = 512) -> dict:
    """Return the smallest watermark region that can hold the delivery token.

    Lets the UI prevent the region box from shrinking below a size that would
    fail to embed. Capacity scales ~linearly with area, so the minimum region
    fraction is ``token_bits / capacity(full-frame)`` with a safety margin.

    Args:
        model: Watermark model id.
        width: Media width in pixels.
        height: Media height in pixels.

    Returns:
        ``{token_bits, capacity_full_bits, fits, min_w_frac, min_h_frac}``.
    """
    from app.payload.service import TokenCodec

    try:
        engine = engine_registry.get_engine(model)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    width = max(1, int(width))
    height = max(1, int(height))
    token_bits = TokenCodec().wire_len() * 8
    cap_full = int(engine.capacity_bits((height, width, 3)))
    fits = cap_full >= token_bits

    if cap_full <= 0:
        side = 1.0
    else:
        frac_area = min(1.0, (token_bits / cap_full) * 1.3)  # 30% safety margin
        side = min(1.0, math.sqrt(frac_area))

    return {
        "model": model,
        "token_bits": token_bits,
        "capacity_full_bits": cap_full,
        "fits": fits,
        "min_w_frac": round(side, 4),
        "min_h_frac": round(side, 4),
    }
