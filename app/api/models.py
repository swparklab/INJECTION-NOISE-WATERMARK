"""Model selector endpoints: list available watermark models."""

from __future__ import annotations

from fastapi import APIRouter

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
