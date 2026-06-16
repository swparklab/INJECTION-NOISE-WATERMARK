"""Tests for watermark pattern generation."""

import torch
import pytest
from tree_ring_watermark.core.patterns import (
    circle_mask,
    square_mask,
    RandomPattern,
    RingPattern,
    ZeroPattern,
    ConstPattern,
    get_watermarking_pattern,
)


def test_circle_mask():
    """Test circular mask generation."""
    mask = circle_mask(size=64, r=10)
    assert mask.shape == (64, 64)
    assert mask.dtype == bool
    assert mask.sum() > 0


def test_square_mask():
    """Test square mask generation."""
    mask = square_mask(size=64, r=10)
    assert mask.shape == (64, 64)
    assert mask.dtype == bool
    assert mask.sum() > 0


def test_random_pattern():
    """Test random pattern generation."""
    device = torch.device("cpu")
    init_tensor = torch.randn(1, 4, 64, 64)

    generator = RandomPattern()
    pattern = generator.generate(init_tensor, device, seed=42, radius=10)

    assert pattern.shape[0] == 1  # Batch size
    assert pattern.dtype in [torch.complex64, torch.complex128]


def test_ring_pattern():
    """Test ring pattern generation."""
    device = torch.device("cpu")
    init_tensor = torch.randn(1, 4, 64, 64)

    generator = RingPattern()
    pattern = generator.generate(init_tensor, device, seed=42, radius=10)

    assert pattern.shape[0] == 1
    assert pattern.dtype in [torch.complex64, torch.complex128]


def test_zero_pattern():
    """Test zero pattern generation."""
    device = torch.device("cpu")
    init_tensor = torch.randn(1, 4, 64, 64)

    generator = ZeroPattern()
    pattern = generator.generate(init_tensor, device, seed=42, radius=10)

    assert pattern.shape[0] == 1
    assert torch.allclose(pattern, torch.zeros_like(pattern))


def test_const_pattern():
    """Test constant pattern generation."""
    device = torch.device("cpu")
    init_tensor = torch.randn(1, 4, 64, 64)
    const_value = 5.0

    generator = ConstPattern(const_value=const_value)
    pattern = generator.generate(init_tensor, device, seed=42, radius=10)

    assert pattern.shape[0] == 1
    # All non-zero elements should be close to const_value
    non_zero = pattern[pattern != 0]
    if non_zero.numel() > 0:
        assert torch.allclose(non_zero.abs(), torch.full_like(non_zero, const_value).abs())


def test_get_watermarking_pattern():
    """Test pattern factory function."""
    device = torch.device("cpu")
    init_tensor = torch.randn(1, 4, 64, 64)

    pattern = get_watermarking_pattern(
        init_tensor,
        pattern_type="rand",
        device=device,
        seed=42,
        radius=10,
    )

    assert pattern.shape[0] == 1
    assert pattern is not None


def test_get_watermarking_pattern_unknown_type():
    """Test invalid pattern type raises error."""
    device = torch.device("cpu")
    init_tensor = torch.randn(1, 4, 64, 64)

    with pytest.raises(ValueError):
        get_watermarking_pattern(
            init_tensor,
            pattern_type="invalid_pattern",
            device=device,
        )
