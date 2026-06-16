"""Tests for pipeline implementations."""

import pytest
import torch

from tree_ring_watermark.pipelines.base import BaseDiffusionPipeline, PipelineFactory


class MockDiffusionPipeline(BaseDiffusionPipeline):
    """Mock pipeline for testing."""

    def get_random_latents(
        self,
        batch_size=1,
        height=512,
        width=512,
        generator=None,
    ):
        return torch.randn(batch_size, 4, height // 8, width // 8)

    def get_text_embedding(self, prompt):
        return torch.randn(1, 77, 768)

    def get_image_latents(self, image, sample=True, rng_generator=None):
        return torch.randn(1, 4, 64, 64)

    def forward_diffusion(
        self,
        latents,
        text_embeddings,
        guidance_scale=1.0,
        num_inference_steps=50,
    ):
        return latents

    def __call__(self, prompt, **kwargs):
        images = []
        return images, None


def test_pipeline_creation():
    """Test basic pipeline creation."""
    pipeline = MockDiffusionPipeline(model_id="test-model")
    assert pipeline.model_id == "test-model"
    assert pipeline.device is not None


def test_random_latents():
    """Test random latent generation."""
    pipeline = MockDiffusionPipeline(model_id="test-model")
    latents = pipeline.get_random_latents(batch_size=1, height=512, width=512)

    assert latents.shape == (1, 4, 64, 64)
    assert latents.dtype == torch.float32


def test_text_embedding():
    """Test text embedding generation."""
    pipeline = MockDiffusionPipeline(model_id="test-model")
    embeddings = pipeline.get_text_embedding("a test prompt")

    assert embeddings.shape == (1, 77, 768)
    assert embeddings.dtype == torch.float32


def test_image_latents():
    """Test image encoding to latents."""
    pipeline = MockDiffusionPipeline(model_id="test-model")
    image = torch.randn(1, 3, 512, 512)
    latents = pipeline.get_image_latents(image)

    assert latents.shape == (1, 4, 64, 64)


def test_forward_diffusion():
    """Test forward diffusion process."""
    pipeline = MockDiffusionPipeline(model_id="test-model")
    latents = torch.randn(1, 4, 64, 64)
    text_embeddings = torch.randn(1, 77, 768)

    result = pipeline.forward_diffusion(latents, text_embeddings)

    assert result.shape == latents.shape


def test_pipeline_factory_register():
    """Test pipeline factory registration."""
    PipelineFactory.register("mock", MockDiffusionPipeline)

    assert "mock" in PipelineFactory._pipelines


def test_pipeline_factory_create():
    """Test pipeline factory creation."""
    PipelineFactory.register("mock", MockDiffusionPipeline)

    pipeline = PipelineFactory.create("test-model", pipeline_type="mock")

    assert isinstance(pipeline, MockDiffusionPipeline)
    assert pipeline.model_id == "test-model"


def test_pipeline_factory_unknown_type():
    """Test factory with unknown pipeline type."""
    with pytest.raises(ValueError):
        PipelineFactory.create("test-model", pipeline_type="unknown-type")
