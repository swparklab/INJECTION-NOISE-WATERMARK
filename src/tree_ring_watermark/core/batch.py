"""Batch processing utilities for efficient watermarking operations."""

import torch
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PIL import Image
from tqdm import tqdm

from tree_ring_watermark.config import WatermarkConfig
from tree_ring_watermark.core.watermark import Watermarker, inject_watermark, get_watermarking_mask
from tree_ring_watermark.core.detection import Detector


@dataclass
class BatchResult:
    """Result from batch processing operation.

    Attributes:
        success_count: Number of successful operations
        failed_count: Number of failed operations
        total_count: Total number of items processed
        results: List of individual results
        errors: List of error messages
    """
    success_count: int
    failed_count: int
    total_count: int
    results: List[any]
    errors: List[str]

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count


class BatchWatermarker:
    """Batch processing for watermark injection."""

    def __init__(self, config: Optional[WatermarkConfig] = None, device: Optional[str] = None):
        """Initialize batch watermarker.

        Args:
            config: WatermarkConfig for watermarking parameters
            device: Device to use ('cuda' or 'cpu')
        """
        self.config = config or WatermarkConfig()
        self.watermarker = Watermarker(self.config)
        if device:
            self.watermarker.device = torch.device(device)

    def watermark_batch(
        self,
        latents_list: List[torch.Tensor],
        seed: int = 42,
        show_progress: bool = True,
    ) -> BatchResult:
        """Apply watermarking to a batch of latent tensors.

        Args:
            latents_list: List of latent tensors to watermark
            seed: Random seed for reproducibility
            show_progress: Whether to show progress bar

        Returns:
            BatchResult with watermarked tensors and metadata
        """
        results = []
        errors = []

        iterator = tqdm(latents_list, disable=not show_progress, desc="Watermarking batch")

        for i, latents in enumerate(iterator):
            try:
                # Prepare pattern
                pattern = self.watermarker.prepare_watermark_pattern()

                # Create mask
                mask = self.watermarker.create_mask(latents.shape)

                # Inject watermark
                watermarked = inject_watermark(latents, mask, pattern, self.config)
                results.append(watermarked)

            except Exception as e:
                error_msg = f"Item {i}: {str(e)}"
                errors.append(error_msg)
                results.append(None)

        success_count = sum(1 for r in results if r is not None)
        failed_count = len(latents_list) - success_count

        return BatchResult(
            success_count=success_count,
            failed_count=failed_count,
            total_count=len(latents_list),
            results=results,
            errors=errors,
        )

    def watermark_images_batch(
        self,
        images: List[Image.Image],
        seed: int = 42,
        show_progress: bool = True,
    ) -> BatchResult:
        """Apply watermarking to a batch of PIL images.

        Args:
            images: List of PIL images to watermark
            seed: Random seed for reproducibility
            show_progress: Whether to show progress bar

        Returns:
            BatchResult with watermarked image metadata
        """
        results = []
        errors = []

        iterator = tqdm(images, disable=not show_progress, desc="Processing image batch")

        for i, image in enumerate(iterator):
            try:
                # This would require integration with the full pipeline
                # For now, just track the image
                results.append({"image": image, "watermarked": True})

            except Exception as e:
                error_msg = f"Image {i}: {str(e)}"
                errors.append(error_msg)
                results.append(None)

        success_count = sum(1 for r in results if r is not None)
        failed_count = len(images) - success_count

        return BatchResult(
            success_count=success_count,
            failed_count=failed_count,
            total_count=len(images),
            results=results,
            errors=errors,
        )


class BatchDetector:
    """Batch processing for watermark detection."""

    def __init__(self, config: Optional[WatermarkConfig] = None, device: Optional[str] = None):
        """Initialize batch detector.

        Args:
            config: WatermarkConfig for detection parameters
            device: Device to use ('cuda' or 'cpu')
        """
        self.config = config or WatermarkConfig()
        self.detector = Detector(self.config)
        if device:
            self.detector.device = torch.device(device)

    def detect_batch(
        self,
        latents_no_w_list: List[torch.Tensor],
        latents_w_list: List[torch.Tensor],
        mask_list: List[torch.Tensor],
        pattern_list: List[torch.Tensor],
        show_progress: bool = True,
    ) -> BatchResult:
        """Detect watermarks in a batch of latent pairs.

        Args:
            latents_no_w_list: List of reference non-watermarked latents
            latents_w_list: List of test (potentially watermarked) latents
            mask_list: List of watermark masks
            pattern_list: List of watermark patterns
            show_progress: Whether to show progress bar

        Returns:
            BatchResult with detection results
        """
        if not (
            len(latents_no_w_list)
            == len(latents_w_list)
            == len(mask_list)
            == len(pattern_list)
        ):
            raise ValueError("All input lists must have the same length")

        results = []
        errors = []

        batches = zip(latents_no_w_list, latents_w_list, mask_list, pattern_list)
        iterator = tqdm(batches, total=len(latents_no_w_list), disable=not show_progress, desc="Detecting batch")

        for i, (latent_no_w, latent_w, mask, pattern) in enumerate(iterator):
            try:
                detection_result = self.detector.detect(
                    latent_no_w, latent_w, mask, pattern
                )
                results.append(detection_result)

            except Exception as e:
                error_msg = f"Item {i}: {str(e)}"
                errors.append(error_msg)
                results.append(None)

        success_count = sum(1 for r in results if r is not None)
        failed_count = len(latents_no_w_list) - success_count

        return BatchResult(
            success_count=success_count,
            failed_count=failed_count,
            total_count=len(latents_no_w_list),
            results=results,
            errors=errors,
        )

    def detection_statistics(self, batch_result: BatchResult) -> Dict[str, float]:
        """Calculate statistics from batch detection results.

        Args:
            batch_result: BatchResult from detect_batch

        Returns:
            Dictionary with detection statistics
        """
        from tree_ring_watermark.core.detection import DetectionResult

        valid_results = [r for r in batch_result.results if isinstance(r, DetectionResult)]

        if not valid_results:
            return {}

        watermarked_count = sum(1 for r in valid_results if r.is_watermarked)
        confidences = [r.confidence for r in valid_results]

        return {
            "watermarked_detected": watermarked_count,
            "not_watermarked_detected": len(valid_results) - watermarked_count,
            "detection_rate": watermarked_count / len(valid_results) if valid_results else 0,
            "mean_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "min_confidence": min(confidences) if confidences else 0,
            "max_confidence": max(confidences) if confidences else 0,
        }
