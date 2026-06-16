"""Watermark backend adapters (neural + diffusion) behind the engine interface."""

from collections.abc import Callable

from app.core.base import WatermarkEngine


def register_adapters(register: Callable[[str, Callable[[], WatermarkEngine]], None]) -> None:
    """Register all adapter engines with the engine registry.

    Args:
        register: ``register_engine(model_id, factory)`` callable.
    """
    from app.adapters.diffusion_adapters import (
        GaussianShadingAdapter,
        RingIDAdapter,
        TreeRingAdapter,
    )
    from app.adapters.neural_adapters import (
        InvisMarkAdapter,
        MetaSealAdapter,
        VideoSealAdapter,
        WAMAdapter,
    )

    register("videoseal", VideoSealAdapter)
    register("metaseal", MetaSealAdapter)
    register("invismark", InvisMarkAdapter)
    register("wam", WAMAdapter)
    register("tree-ring", TreeRingAdapter)
    register("gaussian-shading", GaussianShadingAdapter)
    register("ringid", RingIDAdapter)
