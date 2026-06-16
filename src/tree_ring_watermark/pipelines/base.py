"""Base classes for diffusion model pipelines."""

from abc import ABC, abstractmethod
from typing import Optional, Union, List, Tuple

import torch
from PIL import Image
from torchvision import transforms


class BaseDiffusionPipeline(ABC):
    """Abstract base class for diffusion model pipelines.

    Defines the interface that all diffusion pipelines must implement
    for watermarking and image generation.
    """

    def __init__(self, model_id: str, device: Optional[str] = None):
        """Initialize pipeline.

        Args:
            model_id: Hugging Face model identifier
            device: Device to use ('cuda' or 'cpu')
        """
        self.model_id = model_id
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)

    @abstractmethod
    def get_random_latents(
        self,
        batch_size: int = 1,
        height: int = 512,
        width: int = 512,
        generator: Optional[torch.Generator] = None,
    ) -> torch.Tensor:
        """Generate random latent vectors.

        Args:
            batch_size: Batch size
            height: Image height in pixels
            width: Image width in pixels
            generator: Random generator for reproducibility

        Returns:
            Random latent tensor
        """
        pass

    @abstractmethod
    def get_text_embedding(self, prompt: str) -> torch.Tensor:
        """Encode text prompt to embeddings.

        Args:
            prompt: Text prompt

        Returns:
            Text embedding tensor
        """
        pass

    @abstractmethod
    def get_image_latents(
        self,
        image: torch.Tensor,
        sample: bool = True,
    ) -> torch.Tensor:
        """Encode image to latent space.

        Args:
            image: Image tensor in range [-1, 1]
            sample: Whether to sample or use mean

        Returns:
            Latent encoding
        """
        pass

    @abstractmethod
    def forward_diffusion(
        self,
        latents: torch.Tensor,
        text_embeddings: torch.Tensor,
        guidance_scale: float = 1.0,
        num_inference_steps: int = 50,
    ) -> torch.Tensor:
        """Forward diffusion process (image to noise).

        Args:
            latents: Starting latent tensor
            text_embeddings: Text embeddings for guidance
            guidance_scale: Guidance scale
            num_inference_steps: Number of diffusion steps

        Returns:
            Reversed latents (noisy representation)
        """
        pass

    @abstractmethod
    def __call__(
        self,
        prompt: str,
        num_images_per_prompt: int = 1,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 50,
        height: Optional[int] = None,
        width: Optional[int] = None,
        latents: Optional[torch.Tensor] = None,
    ) -> Tuple[List[Image.Image], Optional[torch.Tensor]]:
        """Generate images from text prompt.

        Args:
            prompt: Text prompt
            num_images_per_prompt: Number of images per prompt
            guidance_scale: Guidance scale
            num_inference_steps: Number of diffusion steps
            height: Image height
            width: Image width
            latents: Pre-generated latents

        Returns:
            Tuple of (images, init_latents)
        """
        pass

    def decode_latents(self, latents: torch.Tensor) -> torch.Tensor:
        """Decode latents to pixel space.

        Args:
            latents: Latent tensor

        Returns:
            Image tensor in range [0, 1]
        """
        raise NotImplementedError

    def encode_image(self, image: Image.Image) -> torch.Tensor:
        """Encode PIL image to tensor.

        Args:
            image: PIL Image

        Returns:
            Tensor in range [-1, 1]
        """
        tform = transforms.Compose([
            transforms.Resize(512),
            transforms.CenterCrop(512),
            transforms.ToTensor(),
        ])
        tensor = tform(image)
        return 2.0 * tensor - 1.0


class PipelineFactory:
    """Factory for creating diffusion pipelines."""

    _pipelines = {}

    @classmethod
    def register(cls, name: str, pipeline_class):
        """Register a pipeline class.

        Args:
            name: Name identifier for pipeline
            pipeline_class: Pipeline class
        """
        cls._pipelines[name] = pipeline_class

    @classmethod
    def create(
        cls,
        model_id: str,
        pipeline_type: str = "stable-diffusion",
        **kwargs,
    ) -> BaseDiffusionPipeline:
        """Create a pipeline instance.

        Args:
            model_id: Model identifier
            pipeline_type: Type of pipeline
            **kwargs: Additional arguments for pipeline

        Returns:
            Pipeline instance
        """
        if pipeline_type not in cls._pipelines:
            raise ValueError(
                f"Unknown pipeline type: {pipeline_type}. "
                f"Available: {list(cls._pipelines.keys())}"
            )

        pipeline_class = cls._pipelines[pipeline_type]
        return pipeline_class(model_id, **kwargs)
