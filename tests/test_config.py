"""Tests for configuration classes."""

import pytest
from tree_ring_watermark.config import WatermarkConfig


def test_watermark_config_default():
    """Test default WatermarkConfig creation."""
    config = WatermarkConfig()
    assert config.w_seed == 999999
    assert config.w_radius == 10
    assert config.w_pattern == "rand"
    assert config.w_mask_shape == "circle"


def test_watermark_config_custom():
    """Test custom WatermarkConfig."""
    config = WatermarkConfig(
        w_seed=12345,
        w_radius=20,
        w_pattern="ring",
    )
    assert config.w_seed == 12345
    assert config.w_radius == 20
    assert config.w_pattern == "ring"


def test_watermark_config_validate():
    """Test WatermarkConfig validation."""
    config = WatermarkConfig()
    config.validate()

    with pytest.raises(ValueError):
        bad_config = WatermarkConfig(w_radius=-1)
        bad_config.validate()

    with pytest.raises(ValueError):
        bad_config = WatermarkConfig(w_channel=-2)
        bad_config.validate()

    with pytest.raises(ValueError):
        bad_config = WatermarkConfig(image_length=1024)
        bad_config.validate()


def test_watermark_config_distortion_params():
    """Test distortion parameters."""
    config = WatermarkConfig(
        r_degree=45.0,
        jpeg_ratio=75,
        gaussian_blur_r=5,
        gaussian_std=0.1,
    )
    assert config.r_degree == 45.0
    assert config.jpeg_ratio == 75
    assert config.gaussian_blur_r == 5
    assert config.gaussian_std == 0.1
