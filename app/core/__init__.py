"""Core watermark engines and services."""

from app.core.base import DetectResult, EmbedResult, WatermarkEngine
from app.core.detection_engine import DetectionEngine, TokenDetection
from app.core.removal_engine import RemovalEngine, RemovalResult
from app.core.tracking_engine import TrackingEngine, TraceResult
from app.core.watermark_engine import EmbedOutcome, WatermarkService

__all__ = [
    "WatermarkEngine",
    "EmbedResult",
    "DetectResult",
    "WatermarkService",
    "EmbedOutcome",
    "DetectionEngine",
    "TokenDetection",
    "TrackingEngine",
    "TraceResult",
    "RemovalEngine",
    "RemovalResult",
]
