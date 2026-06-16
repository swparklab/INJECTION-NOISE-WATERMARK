"""Core watermarking functionality for diffusion models."""

import copy
import json
import random
import numpy as np
import torch
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ImageFilter
from torchvision import transforms
import scipy.stats

from tree_ring_watermark.config import WatermarkConfig
from tree_ring_watermark.core.patterns import get_watermarking_pattern, circle_mask


@dataclass
class WatermarkInfo:
    """Information about injected watermark.

    Attributes:
        config: WatermarkConfig used for injection
        seed: Random seed used
        pattern_shape: Shape of generated pattern
        injection_method: Method used ('complex' or 'seed')
    """
    config: WatermarkConfig
    seed: int
    pattern_shape: Tuple[int, ...]
    injection_method: str


def set_random_seed(seed: int = 0) -> None:
    """Set random seeds for reproducibility.

    Args:
        seed: Base seed value
    """
    torch.manual_seed(seed + 0)
    torch.cuda.manual_seed(seed + 1)
    torch.cuda.manual_seed_all(seed + 2)
    np.random.seed(seed + 3)
    torch.cuda.manual_seed_all(seed + 4)
    random.seed(seed + 5)


def transform_img(image: Image.Image, target_size: int = 512) -> torch.Tensor:
    """Transform PIL image to normalized tensor.

    Args:
        image: PIL Image object
        target_size: Target size for resizing

    Returns:
        Normalized tensor in range [-1, 1]
    """
    tform = transforms.Compose([
        transforms.Resize(target_size),
        transforms.CenterCrop(target_size),
        transforms.ToTensor(),
    ])
    image_tensor = tform(image)
    return 2.0 * image_tensor - 1.0


def get_watermarking_mask(
    init_latents: torch.Tensor,
    config: WatermarkConfig,
    device: torch.device,
) -> torch.Tensor:
    """Generate watermarking mask for latent space.

    Args:
        init_latents: Initial latent tensor
        config: WatermarkConfig with mask parameters
        device: PyTorch device

    Returns:
        Boolean mask tensor indicating where to inject watermark
    """
    watermarking_mask = torch.zeros(init_latents.shape, dtype=torch.bool).to(device)

    if config.w_mask_shape == "circle":
        np_mask = circle_mask(init_latents.shape[-1], r=config.w_radius)
        torch_mask = torch.tensor(np_mask, dtype=torch.bool).to(device)

        if config.w_channel == -1:
            watermarking_mask[:, :] = torch_mask
        else:
            watermarking_mask[:, config.w_channel] = torch_mask

    elif config.w_mask_shape == "square":
        anchor_p = init_latents.shape[-1] // 2
        if config.w_channel == -1:
            watermarking_mask[
                :, :,
                anchor_p - config.w_radius:anchor_p + config.w_radius,
                anchor_p - config.w_radius:anchor_p + config.w_radius
            ] = True
        else:
            watermarking_mask[
                :, config.w_channel,
                anchor_p - config.w_radius:anchor_p + config.w_radius,
                anchor_p - config.w_radius:anchor_p + config.w_radius
            ] = True
    elif config.w_mask_shape == "no":
        pass
    else:
        raise ValueError(f"Unknown mask shape: {config.w_mask_shape}")

    return watermarking_mask


def inject_watermark(
    init_latents: torch.Tensor,
    watermarking_mask: torch.Tensor,
    gt_patch: torch.Tensor,
    config: WatermarkConfig,
) -> torch.Tensor:
    """Inject watermark into latent tensor.

    Args:
        init_latents: Initial latent tensor
        watermarking_mask: Mask indicating injection locations
        gt_patch: Pattern to inject
        config: WatermarkConfig with injection method

    Returns:
        Watermarked latent tensor
    """
    if config.w_injection == "complex":
        init_latents_fft = torch.fft.fftshift(torch.fft.fft2(init_latents), dim=(-1, -2))
        init_latents_fft[watermarking_mask] = gt_patch[watermarking_mask].clone()
        init_latents = torch.fft.ifft2(torch.fft.ifftshift(init_latents_fft, dim=(-1, -2))).real

    elif config.w_injection == "seed":
        init_latents[watermarking_mask] = gt_patch[watermarking_mask].clone()

    else:
        raise ValueError(f"Unknown injection method: {config.w_injection}")

    return init_latents


def image_distortion(
    img1: Image.Image,
    img2: Image.Image,
    seed: int,
    config: WatermarkConfig,
) -> Tuple[Image.Image, Image.Image]:
    """Apply distortions to images for robustness testing.

    Args:
        img1: First image
        img2: Second image
        seed: Random seed for reproducible distortions
        config: WatermarkConfig with distortion parameters

    Returns:
        Tuple of distorted images
    """
    if config.r_degree is not None:
        img1 = transforms.RandomRotation((config.r_degree, config.r_degree))(img1)
        img2 = transforms.RandomRotation((config.r_degree, config.r_degree))(img2)

    if config.jpeg_ratio is not None:
        tmp_file = f"tmp_{config.jpeg_ratio}.jpg"
        img1.save(tmp_file, quality=config.jpeg_ratio)
        img1 = Image.open(tmp_file)
        img2.save(tmp_file, quality=config.jpeg_ratio)
        img2 = Image.open(tmp_file)

    if config.crop_scale is not None and config.crop_ratio is not None:
        set_random_seed(seed)
        img1 = transforms.RandomResizedCrop(
            img1.size,
            scale=(config.crop_scale, config.crop_scale),
            ratio=(config.crop_ratio, config.crop_ratio),
        )(img1)
        set_random_seed(seed)
        img2 = transforms.RandomResizedCrop(
            img2.size,
            scale=(config.crop_scale, config.crop_scale),
            ratio=(config.crop_ratio, config.crop_ratio),
        )(img2)

    if config.gaussian_blur_r is not None:
        img1 = img1.filter(ImageFilter.GaussianBlur(radius=config.gaussian_blur_r))
        img2 = img2.filter(ImageFilter.GaussianBlur(radius=config.gaussian_blur_r))

    if config.gaussian_std is not None:
        img_shape = np.array(img1).shape
        g_noise = np.random.normal(0, config.gaussian_std, img_shape) * 255
        g_noise = g_noise.astype(np.uint8)
        img1 = Image.fromarray(np.clip(np.array(img1) + g_noise, 0, 255))
        img2 = Image.fromarray(np.clip(np.array(img2) + g_noise, 0, 255))

    if config.brightness_factor is not None:
        img1 = transforms.ColorJitter(brightness=config.brightness_factor)(img1)
        img2 = transforms.ColorJitter(brightness=config.brightness_factor)(img2)

    return img1, img2


def eval_watermark(
    reversed_latents_no_w: torch.Tensor,
    reversed_latents_w: torch.Tensor,
    watermarking_mask: torch.Tensor,
    gt_patch: torch.Tensor,
    config: WatermarkConfig,
) -> Tuple[float, float]:
    """Evaluate watermark presence by comparing FFT space metrics.

    Args:
        reversed_latents_no_w: Reversed latents from non-watermarked image
        reversed_latents_w: Reversed latents from watermarked image
        watermarking_mask: Mask indicating watermark region
        gt_patch: Ground truth watermark pattern
        config: WatermarkConfig with measurement method

    Returns:
        Tuple of (no_w_metric, w_metric) where lower values indicate watermark presence
    """
    if "complex" in config.w_measurement:
        reversed_latents_no_w_fft = torch.fft.fftshift(torch.fft.fft2(reversed_latents_no_w), dim=(-1, -2))
        reversed_latents_w_fft = torch.fft.fftshift(torch.fft.fft2(reversed_latents_w), dim=(-1, -2))
        target_patch = gt_patch
    elif "seed" in config.w_measurement:
        reversed_latents_no_w_fft = reversed_latents_no_w
        reversed_latents_w_fft = reversed_latents_w
        target_patch = gt_patch
    else:
        raise ValueError(f"Unknown measurement method: {config.w_measurement}")

    if "l1" in config.w_measurement:
        no_w_metric = torch.abs(reversed_latents_no_w_fft[watermarking_mask] - target_patch[watermarking_mask]).mean().item()
        w_metric = torch.abs(reversed_latents_w_fft[watermarking_mask] - target_patch[watermarking_mask]).mean().item()
    else:
        raise ValueError(f"Unknown measurement method: {config.w_measurement}")

    return no_w_metric, w_metric


def get_p_value(
    reversed_latents_no_w: torch.Tensor,
    reversed_latents_w: torch.Tensor,
    watermarking_mask: torch.Tensor,
    gt_patch: torch.Tensor,
    config: WatermarkConfig,
) -> Tuple[float, float]:
    """Calculate statistical p-values for watermark detection.

    Args:
        reversed_latents_no_w: Reversed latents from non-watermarked image
        reversed_latents_w: Reversed latents from watermarked image
        watermarking_mask: Mask indicating watermark region
        gt_patch: Ground truth watermark pattern
        config: WatermarkConfig

    Returns:
        Tuple of (p_no_w, p_w) - p-values for non-watermarked and watermarked images
    """
    reversed_latents_no_w_fft = torch.fft.fftshift(torch.fft.fft2(reversed_latents_no_w), dim=(-1, -2))[watermarking_mask].flatten()
    reversed_latents_w_fft = torch.fft.fftshift(torch.fft.fft2(reversed_latents_w), dim=(-1, -2))[watermarking_mask].flatten()
    target_patch = gt_patch[watermarking_mask].flatten()

    target_patch_concat = torch.concatenate([target_patch.real, target_patch.imag])

    # Non-watermarked case
    reversed_latents_no_w_concat = torch.concatenate([reversed_latents_no_w_fft.real, reversed_latents_no_w_fft.imag])
    sigma_no_w = reversed_latents_no_w_concat.std()
    lambda_no_w = (target_patch_concat ** 2 / sigma_no_w ** 2).sum().item()
    x_no_w = (((reversed_latents_no_w_concat - target_patch_concat) / sigma_no_w) ** 2).sum().item()
    p_no_w = scipy.stats.ncx2.cdf(x=x_no_w, df=len(target_patch_concat), nc=lambda_no_w)

    # Watermarked case
    reversed_latents_w_concat = torch.concatenate([reversed_latents_w_fft.real, reversed_latents_w_fft.imag])
    sigma_w = reversed_latents_w_concat.std()
    lambda_w = (target_patch_concat ** 2 / sigma_w ** 2).sum().item()
    x_w = (((reversed_latents_w_concat - target_patch_concat) / sigma_w) ** 2).sum().item()
    p_w = scipy.stats.ncx2.cdf(x=x_w, df=len(target_patch_concat), nc=lambda_w)

    return p_no_w, p_w


class Watermarker:
    """Main class for injecting watermarks into diffusion-generated images."""

    def __init__(self, config: Optional[WatermarkConfig] = None):
        """Initialize Watermarker.

        Args:
            config: WatermarkConfig instance (uses defaults if None)
        """
        self.config = config or WatermarkConfig()
        self.config.validate()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def prepare_watermark_pattern(self) -> torch.Tensor:
        """Prepare watermark pattern based on configuration.

        Returns:
            Generated watermark pattern tensor
        """
        set_random_seed(self.config.w_seed)
        init_tensor = torch.randn(1, 4, 64, 64, device=self.device)

        pattern = get_watermarking_pattern(
            init_tensor,
            pattern_type=self.config.w_pattern,
            device=self.device,
            seed=self.config.w_seed,
            radius=self.config.w_radius,
            pattern_const=self.config.w_pattern_const,
        )
        return pattern

    def create_mask(self, latent_shape: Tuple[int, ...]) -> torch.Tensor:
        """Create watermark mask for given latent shape.

        Args:
            latent_shape: Shape of latent tensor

        Returns:
            Boolean mask tensor
        """
        dummy_latents = torch.zeros(latent_shape, device=self.device)
        return get_watermarking_mask(dummy_latents, self.config, self.device)
