"""Watermark detection and measurement functionality."""

import torch
from dataclasses import dataclass
from typing import Optional, Tuple

from tree_ring_watermark.config import WatermarkConfig
from tree_ring_watermark.core.watermark import eval_watermark, get_p_value


@dataclass
class DetectionResult:
    """Result of watermark detection.

    Attributes:
        is_watermarked: Boolean indicating if watermark was detected
        confidence: Confidence score (0-1)
        no_w_metric: Metric from non-watermarked comparison
        w_metric: Metric from watermarked comparison
        p_value: Statistical p-value for detection
        threshold: Detection threshold used
    """
    is_watermarked: bool
    confidence: float
    no_w_metric: float
    w_metric: float
    p_value: Optional[float] = None
    threshold: float = 0.5


class Detector:
    """Class for detecting watermarks in images."""

    def __init__(
        self,
        config: Optional[WatermarkConfig] = None,
        threshold: float = 0.5,
    ):
        """Initialize Detector.

        Args:
            config: WatermarkConfig instance
            threshold: Detection threshold (0-1)
        """
        self.config = config or WatermarkConfig()
        self.config.validate()
        self.threshold = threshold
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def detect(
        self,
        reversed_latents_no_w: torch.Tensor,
        reversed_latents_w: torch.Tensor,
        watermarking_mask: torch.Tensor,
        gt_patch: torch.Tensor,
    ) -> DetectionResult:
        """Detect watermark using reversed latents.

        Args:
            reversed_latents_no_w: Reversed latents from non-watermarked reference
            reversed_latents_w: Reversed latents from image to test
            watermarking_mask: Mask indicating watermark region
            gt_patch: Ground truth watermark pattern

        Returns:
            DetectionResult object with detection metrics
        """
        no_w_metric, w_metric = eval_watermark(
            reversed_latents_no_w,
            reversed_latents_w,
            watermarking_mask,
            gt_patch,
            self.config,
        )

        p_no_w, p_w = get_p_value(
            reversed_latents_no_w,
            reversed_latents_w,
            watermarking_mask,
            gt_patch,
            self.config,
        )

        confidence = 1.0 - (w_metric / (no_w_metric + 1e-10))
        confidence = max(0.0, min(1.0, confidence))

        is_watermarked = confidence >= self.threshold

        return DetectionResult(
            is_watermarked=is_watermarked,
            confidence=confidence,
            no_w_metric=no_w_metric,
            w_metric=w_metric,
            p_value=p_w,
            threshold=self.threshold,
        )

    def measure_robustness(
        self,
        reversed_latents_no_w: torch.Tensor,
        reversed_latents_w: torch.Tensor,
        watermarking_mask: torch.Tensor,
        gt_patch: torch.Tensor,
    ) -> Tuple[float, float]:
        """Measure robustness metrics.

        Args:
            reversed_latents_no_w: Reversed latents from non-watermarked reference
            reversed_latents_w: Reversed latents from watermarked image
            watermarking_mask: Mask indicating watermark region
            gt_patch: Ground truth watermark pattern

        Returns:
            Tuple of (no_w_metric, w_metric)
        """
        return eval_watermark(
            reversed_latents_no_w,
            reversed_latents_w,
            watermarking_mask,
            gt_patch,
            self.config,
        )
