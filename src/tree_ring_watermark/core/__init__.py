"""Core watermarking functionality."""

from tree_ring_watermark.core.batch import BatchDetector, BatchResult, BatchWatermarker
from tree_ring_watermark.core.detection import Detector, DetectionResult
from tree_ring_watermark.core.robustness import RobustnessEvaluator, RobustnessMetrics
from tree_ring_watermark.core.watermark import Watermarker, WatermarkInfo

__all__ = [
    "Watermarker",
    "Detector",
    "WatermarkInfo",
    "DetectionResult",
    "BatchWatermarker",
    "BatchDetector",
    "BatchResult",
    "RobustnessEvaluator",
    "RobustnessMetrics",
]
