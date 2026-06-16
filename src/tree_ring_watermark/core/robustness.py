"""Robustness testing and metrics for watermark evaluation."""

import numpy as np
import torch
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from PIL import Image

from tree_ring_watermark.config import WatermarkConfig
from tree_ring_watermark.core.watermark import image_distortion, eval_watermark


@dataclass
class RobustnessMetrics:
    """Metrics for watermark robustness evaluation.

    Attributes:
        attack_type: Type of attack applied
        detection_accuracy: Accuracy of detection (0-1)
        robustness_score: Overall robustness score (0-1)
        metrics: Dictionary of detailed metrics
        notes: Additional notes about the test
    """
    attack_type: str
    detection_accuracy: float
    robustness_score: float
    metrics: Dict[str, float]
    notes: Optional[str] = None


class RobustnessEvaluator:
    """Evaluate watermark robustness against various attacks.

    Tests watermark survival under common image transformations
    like JPEG compression, rotation, cropping, etc.
    """

    def __init__(self, config: WatermarkConfig):
        """Initialize robustness evaluator.

        Args:
            config: WatermarkConfig for watermarking parameters
        """
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def evaluate_jpeg_robustness(
        self,
        img_no_w: Image.Image,
        img_w: Image.Image,
        seed: int = 42,
        qualities: Optional[List[int]] = None,
    ) -> List[RobustnessMetrics]:
        """Evaluate robustness to JPEG compression.

        Args:
            img_no_w: Non-watermarked reference image
            img_w: Watermarked image
            seed: Random seed for consistency
            qualities: List of JPEG quality levels to test

        Returns:
            List of RobustnessMetrics for each quality level
        """
        if qualities is None:
            qualities = [95, 85, 75, 50, 25]

        results = []
        for quality in qualities:
            config = WatermarkConfig(**self.config.__dict__)
            config.jpeg_ratio = quality

            img_w_distorted, img_no_w_distorted = image_distortion(
                img_w, img_no_w, seed, config
            )

            # Evaluate detection
            accuracy = self._evaluate_detection(img_no_w_distorted, img_w_distorted)

            metrics = RobustnessMetrics(
                attack_type=f"JPEG compression (quality={quality})",
                detection_accuracy=accuracy,
                robustness_score=accuracy,  # Simplified for now
                metrics={"quality": quality, "accuracy": accuracy},
                notes=f"Tested JPEG compression at quality {quality}%",
            )
            results.append(metrics)

        return results

    def evaluate_rotation_robustness(
        self,
        img_no_w: Image.Image,
        img_w: Image.Image,
        seed: int = 42,
        degrees: Optional[List[float]] = None,
    ) -> List[RobustnessMetrics]:
        """Evaluate robustness to rotation.

        Args:
            img_no_w: Non-watermarked reference image
            img_w: Watermarked image
            seed: Random seed for consistency
            degrees: List of rotation angles to test

        Returns:
            List of RobustnessMetrics for each rotation angle
        """
        if degrees is None:
            degrees = [15, 30, 45]

        results = []
        for degree in degrees:
            config = WatermarkConfig(**self.config.__dict__)
            config.r_degree = float(degree)

            img_w_distorted, img_no_w_distorted = image_distortion(
                img_w, img_no_w, seed, config
            )

            accuracy = self._evaluate_detection(img_no_w_distorted, img_w_distorted)

            metrics = RobustnessMetrics(
                attack_type=f"Rotation ({degree}°)",
                detection_accuracy=accuracy,
                robustness_score=accuracy,
                metrics={"degree": degree, "accuracy": accuracy},
                notes=f"Tested rotation at {degree} degrees",
            )
            results.append(metrics)

        return results

    def evaluate_cropping_robustness(
        self,
        img_no_w: Image.Image,
        img_w: Image.Image,
        seed: int = 42,
        scales: Optional[List[float]] = None,
    ) -> List[RobustnessMetrics]:
        """Evaluate robustness to cropping.

        Args:
            img_no_w: Non-watermarked reference image
            img_w: Watermarked image
            seed: Random seed for consistency
            scales: List of crop scale ratios to test (0-1)

        Returns:
            List of RobustnessMetrics for each crop scale
        """
        if scales is None:
            scales = [0.9, 0.75, 0.5]

        results = []
        for scale in scales:
            config = WatermarkConfig(**self.config.__dict__)
            config.crop_scale = scale
            config.crop_ratio = (1.0, 1.0)  # Square crop

            img_w_distorted, img_no_w_distorted = image_distortion(
                img_w, img_no_w, seed, config
            )

            accuracy = self._evaluate_detection(img_no_w_distorted, img_w_distorted)

            metrics = RobustnessMetrics(
                attack_type=f"Cropping (scale={scale})",
                detection_accuracy=accuracy,
                robustness_score=accuracy,
                metrics={"scale": scale, "accuracy": accuracy},
                notes=f"Tested random resized crop at scale {scale}",
            )
            results.append(metrics)

        return results

    def evaluate_noise_robustness(
        self,
        img_no_w: Image.Image,
        img_w: Image.Image,
        seed: int = 42,
        noise_levels: Optional[List[float]] = None,
    ) -> List[RobustnessMetrics]:
        """Evaluate robustness to Gaussian noise.

        Args:
            img_no_w: Non-watermarked reference image
            img_w: Watermarked image
            seed: Random seed for consistency
            noise_levels: List of noise standard deviations to test

        Returns:
            List of RobustnessMetrics for each noise level
        """
        if noise_levels is None:
            noise_levels = [0.01, 0.05, 0.1]

        results = []
        for noise_std in noise_levels:
            config = WatermarkConfig(**self.config.__dict__)
            config.gaussian_std = noise_std

            img_w_distorted, img_no_w_distorted = image_distortion(
                img_w, img_no_w, seed, config
            )

            accuracy = self._evaluate_detection(img_no_w_distorted, img_w_distorted)

            metrics = RobustnessMetrics(
                attack_type=f"Gaussian noise (std={noise_std})",
                detection_accuracy=accuracy,
                robustness_score=accuracy,
                metrics={"std": noise_std, "accuracy": accuracy},
                notes=f"Tested Gaussian noise with std={noise_std}",
            )
            results.append(metrics)

        return results

    def evaluate_blur_robustness(
        self,
        img_no_w: Image.Image,
        img_w: Image.Image,
        seed: int = 42,
        radii: Optional[List[int]] = None,
    ) -> List[RobustnessMetrics]:
        """Evaluate robustness to Gaussian blur.

        Args:
            img_no_w: Non-watermarked reference image
            img_w: Watermarked image
            seed: Random seed for consistency
            radii: List of blur radius values to test

        Returns:
            List of RobustnessMetrics for each blur radius
        """
        if radii is None:
            radii = [2, 3, 5]

        results = []
        for radius in radii:
            config = WatermarkConfig(**self.config.__dict__)
            config.gaussian_blur_r = radius

            img_w_distorted, img_no_w_distorted = image_distortion(
                img_w, img_no_w, seed, config
            )

            accuracy = self._evaluate_detection(img_no_w_distorted, img_w_distorted)

            metrics = RobustnessMetrics(
                attack_type=f"Gaussian blur (radius={radius})",
                detection_accuracy=accuracy,
                robustness_score=accuracy,
                metrics={"radius": radius, "accuracy": accuracy},
                notes=f"Tested Gaussian blur with radius={radius}",
            )
            results.append(metrics)

        return results

    def _evaluate_detection(
        self,
        img_no_w: Image.Image,
        img_w: Image.Image,
    ) -> float:
        """Evaluate detection success rate (simplified).

        Args:
            img_no_w: Reference non-watermarked image
            img_w: Test watermarked image

        Returns:
            Detection accuracy score (0-1)
        """
        # Simplified evaluation - in practice would use actual detection pipeline
        # This is a placeholder that should be connected to actual detection
        return 1.0  # Placeholder

    def summary(self, results: List[RobustnessMetrics]) -> Dict[str, float]:
        """Generate summary statistics from robustness tests.

        Args:
            results: List of RobustnessMetrics from tests

        Returns:
            Dictionary with summary statistics
        """
        if not results:
            return {}

        accuracies = [r.detection_accuracy for r in results]
        robustness_scores = [r.robustness_score for r in results]

        return {
            "mean_accuracy": np.mean(accuracies),
            "min_accuracy": np.min(accuracies),
            "max_accuracy": np.max(accuracies),
            "std_accuracy": np.std(accuracies),
            "mean_robustness": np.mean(robustness_scores),
            "min_robustness": np.min(robustness_scores),
            "passed_tests": sum(1 for r in results if r.detection_accuracy > 0.8),
            "total_tests": len(results),
        }
