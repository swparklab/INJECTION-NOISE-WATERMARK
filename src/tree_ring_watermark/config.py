"""Configuration classes for watermarking parameters."""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class WatermarkConfig:
    """Configuration for watermark injection and detection.
    
    Attributes:
        w_seed: Random seed for pattern generation
        w_channel: Channel to embed watermark (-1 for all channels)
        w_pattern: Pattern type ('rand', 'ring', 'seed_ring', etc.)
        w_mask_shape: Mask shape ('circle', 'square', 'no')
        w_radius: Radius of circular/square mask in latent space
        w_measurement: Measurement method ('l1_complex', 'l1_seed', etc.)
        w_injection: Injection method ('complex' for FFT domain, 'seed' for latent space)
        w_pattern_const: Constant value for const pattern
        r_degree: Rotation degree for distortion testing
        jpeg_ratio: JPEG quality ratio for distortion testing
        crop_scale: Crop scale for random resized crop
        crop_ratio: Crop ratio for aspect ratio constraint
        gaussian_blur_r: Gaussian blur radius for distortion
        gaussian_std: Gaussian noise standard deviation
        brightness_factor: Brightness adjustment factor
        rand_aug: Number of random augmentations
    """
    
    # Watermark parameters
    w_seed: int = 999999
    w_channel: int = 0
    w_pattern: str = "rand"
    w_mask_shape: Literal["circle", "square", "no"] = "circle"
    w_radius: int = 10
    w_measurement: str = "l1_complex"
    w_injection: Literal["complex", "seed"] = "complex"
    w_pattern_const: float = 0.0
    
    # Distortion parameters for robustness testing
    r_degree: Optional[float] = None
    jpeg_ratio: Optional[int] = None
    crop_scale: Optional[float] = None
    crop_ratio: Optional[float] = None
    gaussian_blur_r: Optional[int] = None
    gaussian_std: Optional[float] = None
    brightness_factor: Optional[float] = None
    rand_aug: int = 0
    
    # Pipeline parameters
    num_inference_steps: int = 50
    guidance_scale: float = 7.5
    image_length: int = 512
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.w_radius <= 0:
            raise ValueError(f"w_radius must be positive, got {self.w_radius}")
        if self.w_channel < -1:
            raise ValueError(f"w_channel must be >= -1, got {self.w_channel}")
        if self.num_inference_steps <= 0:
            raise ValueError(f"num_inference_steps must be positive")
        if self.guidance_scale < 1.0:
            raise ValueError(f"guidance_scale must be >= 1.0")
        if self.image_length not in [256, 512, 768]:
            raise ValueError(f"image_length should be 256, 512, or 768, got {self.image_length}")
