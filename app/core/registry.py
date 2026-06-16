"""Engine registry / model selector.

Central place that maps a model id (``"frequency"``, ``"custom-noise"``,
``"tree-ring"``, ``"videoseal"``, …) to a concrete :class:`WatermarkEngine`
instance. Adapters register themselves here so the API's model selector and the
detection engine can look engines up uniformly.
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.base import WatermarkEngine

_FACTORIES: dict[str, Callable[[], WatermarkEngine]] = {}
_INSTANCES: dict[str, WatermarkEngine] = {}


def register_engine(model_id: str, factory: Callable[[], WatermarkEngine]) -> None:
    """Register an engine factory under ``model_id``."""
    _FACTORIES[model_id] = factory


def get_engine(model_id: str) -> WatermarkEngine:
    """Return a cached engine instance for ``model_id``.

    Raises:
        KeyError: If the model id is not registered.
    """
    if model_id in _INSTANCES:
        return _INSTANCES[model_id]
    if model_id not in _FACTORIES:
        raise KeyError(f"Unknown watermark model: {model_id!r}. Available: {available_models()}")
    engine = _FACTORIES[model_id]()
    _INSTANCES[model_id] = engine
    return engine


def available_models() -> list[str]:
    """List all registered model ids."""
    return sorted(_FACTORIES.keys())


def register_builtin_engines() -> None:
    """Register the engines that ship with the platform.

    Imported lazily so optional heavy dependencies (torch, diffusers) are only
    loaded when those engines are actually instantiated.
    """
    from app.core.frequency_watermark import FrequencyWatermarkEngine
    from app.core.keyed_gaussian import KeyedGaussianEngine

    register_engine("frequency", FrequencyWatermarkEngine)
    register_engine("custom-noise", KeyedGaussianEngine)

    # Adapters (lazy factories — heavy/optional deps imported inside).
    from app.adapters import register_adapters

    register_adapters(register_engine)
