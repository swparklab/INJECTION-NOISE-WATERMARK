"""Watermark pattern generation strategies."""

import copy
import torch
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Tuple


def circle_mask(size: int = 64, r: int = 10, x_offset: int = 0, y_offset: int = 0) -> np.ndarray:
    """Generate a circular mask for watermark injection.
    
    Args:
        size: Size of the mask (size x size)
        r: Radius of the circle
        x_offset: X offset of circle center
        y_offset: Y offset of circle center
        
    Returns:
        Boolean numpy array representing the circular mask
    """
    x0 = y0 = size // 2
    x0 += x_offset
    y0 += y_offset
    y, x = np.ogrid[:size, :size]
    y = y[::-1]
    return ((x - x0)**2 + (y - y0)**2) <= r**2


def square_mask(
    size: int = 64,
    r: int = 10,
    center_x: Optional[int] = None,
    center_y: Optional[int] = None,
) -> np.ndarray:
    """Generate a square mask for watermark injection.
    
    Args:
        size: Size of the mask (size x size)
        r: Half-width of the square
        center_x: X coordinate of center (default: size // 2)
        center_y: Y coordinate of center (default: size // 2)
        
    Returns:
        Boolean numpy array representing the square mask
    """
    if center_x is None:
        center_x = size // 2
    if center_y is None:
        center_y = size // 2
        
    mask = np.zeros((size, size), dtype=bool)
    x_start = max(0, center_x - r)
    x_end = min(size, center_x + r)
    y_start = max(0, center_y - r)
    y_end = min(size, center_y + r)
    mask[y_start:y_end, x_start:x_end] = True
    return mask


class PatternGenerator(ABC):
    """Abstract base class for watermark pattern generation."""
    
    @abstractmethod
    def generate(
        self,
        init_tensor: torch.Tensor,
        device: torch.device,
        seed: int,
        radius: int,
    ) -> torch.Tensor:
        """Generate watermark pattern.
        
        Args:
            init_tensor: Initial random tensor to transform
            device: Device to create tensor on
            seed: Random seed for reproducibility
            radius: Radius parameter for patterns
            
        Returns:
            Generated pattern tensor
        """
        pass


class RandomPattern(PatternGenerator):
    """Random Fourier domain pattern."""
    
    def generate(
        self,
        init_tensor: torch.Tensor,
        device: torch.device,
        seed: int,
        radius: int,
    ) -> torch.Tensor:
        """Generate random FFT pattern."""
        gt_patch = torch.fft.fftshift(torch.fft.fft2(init_tensor), dim=(-1, -2))
        gt_patch[:] = gt_patch[0]  # Copy first channel to all
        return gt_patch


class RingPattern(PatternGenerator):
    """Ring-structured Fourier domain pattern."""
    
    def generate(
        self,
        init_tensor: torch.Tensor,
        device: torch.device,
        seed: int,
        radius: int,
    ) -> torch.Tensor:
        """Generate ring-structured FFT pattern."""
        gt_patch = torch.fft.fftshift(torch.fft.fft2(init_tensor), dim=(-1, -2))
        gt_patch_tmp = copy.deepcopy(gt_patch)
        
        size = init_tensor.shape[-1]
        for i in range(radius, 0, -1):
            tmp_mask = circle_mask(size, r=i)
            tmp_mask = torch.tensor(tmp_mask, dtype=torch.bool).to(device)
            
            for j in range(gt_patch.shape[1]):
                gt_patch[:, j, tmp_mask] = gt_patch_tmp[0, j, 0, i].item()
                
        return gt_patch


class ZeroPattern(PatternGenerator):
    """Zero-valued pattern (no watermark in frequency domain)."""
    
    def generate(
        self,
        init_tensor: torch.Tensor,
        device: torch.device,
        seed: int,
        radius: int,
    ) -> torch.Tensor:
        """Generate zero FFT pattern."""
        gt_patch = torch.fft.fftshift(torch.fft.fft2(init_tensor), dim=(-1, -2)) * 0
        return gt_patch


class ConstPattern(PatternGenerator):
    """Constant-valued pattern."""
    
    def __init__(self, const_value: float = 1.0):
        """Initialize constant pattern.
        
        Args:
            const_value: Constant value to use in pattern
        """
        self.const_value = const_value
    
    def generate(
        self,
        init_tensor: torch.Tensor,
        device: torch.device,
        seed: int,
        radius: int,
    ) -> torch.Tensor:
        """Generate constant FFT pattern."""
        gt_patch = torch.fft.fftshift(torch.fft.fft2(init_tensor), dim=(-1, -2)) * 0
        gt_patch += self.const_value
        return gt_patch


class SeedRingPattern(PatternGenerator):
    """Ring pattern in spatial (latent) domain."""
    
    def generate(
        self,
        init_tensor: torch.Tensor,
        device: torch.device,
        seed: int,
        radius: int,
    ) -> torch.Tensor:
        """Generate ring pattern in latent space."""
        gt_patch = init_tensor
        gt_patch_tmp = copy.deepcopy(gt_patch)
        
        size = init_tensor.shape[-1]
        for i in range(radius, 0, -1):
            tmp_mask = circle_mask(size, r=i)
            tmp_mask = torch.tensor(tmp_mask, dtype=torch.bool).to(device)
            
            for j in range(gt_patch.shape[1]):
                gt_patch[:, j, tmp_mask] = gt_patch_tmp[0, j, 0, i].item()
                
        return gt_patch


def get_watermarking_pattern(
    init_tensor: torch.Tensor,
    pattern_type: str = "rand",
    device: torch.device = torch.device("cpu"),
    seed: int = 999999,
    radius: int = 10,
    pattern_const: float = 0.0,
) -> torch.Tensor:
    """Get watermarking pattern based on type.
    
    Args:
        init_tensor: Initial random tensor
        pattern_type: Type of pattern ('rand', 'ring', 'seed_ring', 'zeros', 'const')
        device: PyTorch device
        seed: Random seed
        radius: Radius parameter
        pattern_const: Constant value for const patterns
        
    Returns:
        Generated watermark pattern tensor
    """
    pattern_generators = {
        "rand": RandomPattern(),
        "ring": RingPattern(),
        "seed_ring": SeedRingPattern(),
        "zeros": ZeroPattern(),
        "const": ConstPattern(pattern_const),
    }
    
    if "seed" in pattern_type:
        if pattern_type == "seed_ring":
            generator = SeedRingPattern()
        elif pattern_type == "seed_zeros":
            return init_tensor * 0
        elif pattern_type == "seed_rand":
            return init_tensor
        else:
            raise ValueError(f"Unknown seed pattern type: {pattern_type}")
    else:
        if pattern_type not in pattern_generators:
            raise ValueError(f"Unknown pattern type: {pattern_type}. Choose from {list(pattern_generators.keys())}")
        generator = pattern_generators[pattern_type]
    
    return generator.generate(init_tensor, device, seed, radius)
