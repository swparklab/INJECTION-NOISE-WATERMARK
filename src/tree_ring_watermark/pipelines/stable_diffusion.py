"""Stable Diffusion pipeline with watermarking support.

This module provides a unified pipeline that supports both forward (generation)
and reverse (image-to-noise) diffusion processes for watermark injection and detection.
"""

from functools import partial
from typing import List, Optional, Tuple, Union

import torch
from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
from diffusers.schedulers import DDIMScheduler, PNDMScheduler, LMSDiscreteScheduler
from PIL import Image

from tree_ring_watermark.pipelines.base import BaseDiffusionPipeline


class StableDiffusionWatermarkPipeline(StableDiffusionPipeline, BaseDiffusionPipeline):
    """Stable Diffusion pipeline with watermarking capabilities.

    Combines the original StableDiffusionPipeline with extensions for:
    - Watermark injection during generation
    - Reverse diffusion (image to noise) for watermark detection
    - Custom latent initialization

    Attributes:
        use_torch_compile: Whether to use torch.compile() for optimization
        compile_backend: Backend for torch.compile (default: 'inductor')
    """

    def __init__(
        self,
        vae,
        text_encoder,
        tokenizer,
        unet,
        scheduler,
        safety_checker,
        feature_extractor,
        requires_safety_checker: bool = True,
        use_torch_compile: bool = False,
        compile_backend: str = "inductor",
    ):
        """Initialize the pipeline.

        Args:
            vae: Variational AutoEncoder for latent encoding/decoding
            text_encoder: Text encoder (CLIP)
            tokenizer: Text tokenizer
            unet: UNet2DConditionModel for diffusion
            scheduler: Noise scheduler (DDIM, PNDM, etc.)
            safety_checker: Safety checker for NSFW content
            feature_extractor: Feature extractor for safety checker
            requires_safety_checker: Whether safety checker is required
            use_torch_compile: Enable torch.compile() optimization
            compile_backend: Backend for torch.compile
        """
        super().__init__(
            vae=vae,
            text_encoder=text_encoder,
            tokenizer=tokenizer,
            unet=unet,
            scheduler=scheduler,
            safety_checker=safety_checker,
            feature_extractor=feature_extractor,
            requires_safety_checker=requires_safety_checker,
        )

        self.use_torch_compile = use_torch_compile
        self.compile_backend = compile_backend

        if use_torch_compile and hasattr(torch, "compile"):
            try:
                self.unet = torch.compile(self.unet, backend=compile_backend)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to compile UNet: {e}. Continuing without compilation.")
                self.use_torch_compile = False

    def get_random_latents(
        self,
        batch_size: int = 1,
        height: int = 512,
        width: int = 512,
        generator: Optional[torch.Generator] = None,
        latents: Optional[torch.FloatTensor] = None,
    ) -> torch.FloatTensor:
        """Generate random latent vectors for diffusion.

        Args:
            batch_size: Batch size for latent generation
            height: Image height (will be divided by vae_scale_factor)
            width: Image width (will be divided by vae_scale_factor)
            generator: Random generator for reproducibility
            latents: Pre-generated latents (if None, generates new ones)

        Returns:
            Random latent tensor of shape (batch_size, 4, height//8, width//8)
        """
        height = height or self.unet.config.sample_size * self.vae_scale_factor
        width = width or self.unet.config.sample_size * self.vae_scale_factor

        batch_size = 1  # Currently only supports batch size 1
        device = self._execution_device

        num_channels_latents = self.unet.in_channels

        latents = self.prepare_latents(
            batch_size,
            num_channels_latents,
            height,
            width,
            self.text_encoder.dtype,
            device,
            generator,
            latents,
        )

        return latents

    @torch.inference_mode()
    def get_text_embedding(self, prompt: str) -> torch.Tensor:
        """Encode text prompt to embeddings.

        Args:
            prompt: Text prompt to encode

        Returns:
            Text embedding tensor of shape (1, seq_len, embed_dim)
        """
        text_input_ids = self.tokenizer(
            prompt,
            padding="max_length",
            truncation=True,
            max_length=self.tokenizer.model_max_length,
            return_tensors="pt",
        ).input_ids

        text_embeddings = self.text_encoder(text_input_ids.to(self.device))[0]
        return text_embeddings

    @torch.inference_mode()
    def get_image_latents(
        self,
        image: torch.Tensor,
        sample: bool = True,
        rng_generator: Optional[torch.Generator] = None,
    ) -> torch.FloatTensor:
        """Encode image to latent space.

        Args:
            image: Image tensor in range [-1, 1]
            sample: Whether to sample or use mode for VAE
            rng_generator: Random generator for sampling

        Returns:
            Latent encoding tensor
        """
        encoding_dist = self.vae.encode(image).latent_dist

        if sample:
            encoding = encoding_dist.sample(generator=rng_generator)
        else:
            encoding = encoding_dist.mode()

        latents = encoding * self.vae.config.scaling_factor
        return latents

    @torch.inference_mode()
    def backward_diffusion(
        self,
        latents: torch.FloatTensor,
        text_embeddings: torch.Tensor,
        guidance_scale: float = 1.0,
        num_inference_steps: int = 50,
        reverse_process: bool = False,
    ) -> torch.FloatTensor:
        """Run diffusion process (forward or reverse).

        Args:
            latents: Starting latent tensor
            text_embeddings: Text embeddings for guidance
            guidance_scale: Guidance scale (1.0 = no guidance)
            num_inference_steps: Number of diffusion steps
            reverse_process: If True, reverses the diffusion (image to noise)

        Returns:
            Resulting latent tensor
        """
        if not isinstance(self.scheduler, (DDIMScheduler, PNDMScheduler, LMSDiscreteScheduler)):
            raise ValueError(
                f"Reverse diffusion only supported for DDIM, PNDM, LMS schedulers. "
                f"Got {type(self.scheduler)}"
            )

        # Set scheduler for inference
        self.scheduler.set_timesteps(num_inference_steps, device=self.device)
        timesteps = self.scheduler.timesteps

        if reverse_process:
            timesteps = torch.flip(timesteps, [0])

        for t in timesteps:
            # Expand latents for guidance
            latent_model_input = torch.cat([latents] * 2)
            latent_model_input = self.scheduler.scale_model_input(latent_model_input, t)

            # Predict noise
            with torch.no_grad():
                noise_pred = self.unet(
                    latent_model_input,
                    t,
                    encoder_hidden_states=text_embeddings,
                ).sample

            # Split guidance
            noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
            noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)

            # Step scheduler
            if reverse_process:
                latents = self.scheduler.add_noise(latents, noise_pred, t)
            else:
                latents = self.scheduler.step(noise_pred, t, latents).prev_sample

        return latents

    # Create forward_diffusion as alias for backward_diffusion with reverse_process=True
    forward_diffusion = partial(backward_diffusion, reverse_process=True)

    @torch.no_grad()
    def __call__(
        self,
        prompt: Union[str, List[str]],
        height: Optional[int] = None,
        width: Optional[int] = None,
        num_inference_steps: int = 50,
        guidance_scale: float = 7.5,
        negative_prompt: Optional[Union[str, List[str]]] = None,
        num_images_per_prompt: int = 1,
        eta: float = 0.0,
        generator: Optional[Union[torch.Generator, List[torch.Generator]]] = None,
        latents: Optional[torch.FloatTensor] = None,
        output_type: str = "pil",
        return_dict: bool = True,
    ) -> Tuple[List[Image.Image], Optional[torch.FloatTensor]]:
        """Generate images from text prompts.

        Args:
            prompt: Text prompt(s) for generation
            height: Image height (default: 512)
            width: Image width (default: 512)
            num_inference_steps: Number of denoising steps
            guidance_scale: Classifier-free guidance scale
            negative_prompt: Negative prompt(s) to guide generation
            num_images_per_prompt: Number of images per prompt
            eta: DDIM parameter (eta = 0 is DDPM, eta = 1 is DDIM)
            generator: Random generator for reproducibility
            latents: Pre-generated latents
            output_type: Output format ('pil' or 'np')
            return_dict: Whether to return dictionary

        Returns:
            Tuple of (images, init_latents) where:
            - images: List of PIL Images or numpy arrays
            - init_latents: Initial latents used (for reproducibility)
        """
        # Set execution device
        if self.device.type == "cpu":
            self._execution_device = self.device
        else:
            self._execution_device = self.device

        # Encode prompt
        text_embeddings = self.encode_prompt(prompt, self.device, num_images_per_prompt)

        # Generate latents
        init_latents = self.get_random_latents(height=height, width=width, generator=generator)
        latents = init_latents.clone()

        # Set scheduler timesteps
        self.scheduler.set_timesteps(num_inference_steps, device=self.device)
        timesteps = self.scheduler.timesteps

        # Denoising loop
        for t in timesteps:
            # Predict noise
            latent_model_input = torch.cat([latents] * 2)
            latent_model_input = self.scheduler.scale_model_input(latent_model_input, t)

            with torch.no_grad():
                noise_pred = self.unet(
                    latent_model_input,
                    t,
                    encoder_hidden_states=text_embeddings,
                ).sample

            # Apply guidance
            noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
            noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)

            # Step scheduler
            latents = self.scheduler.step(noise_pred, t, latents).prev_sample

        # Decode latents
        images = self.decode_latents(latents)

        # Post-processing
        images = self.post_process_image(images, output_type)

        if not return_dict:
            return images, init_latents

        return {
            "images": images,
            "init_latents": init_latents,
        }, init_latents

    def decode_latents(self, latents: torch.FloatTensor) -> torch.Tensor:
        """Decode latents to pixel space.

        Args:
            latents: Latent tensor

        Returns:
            Image tensor in range [0, 1]
        """
        latents = latents / self.vae.config.scaling_factor

        with torch.no_grad():
            image = self.vae.decode(latents).sample

        image = (image / 2 + 0.5).clamp(0, 1)
        return image

    def post_process_image(
        self,
        image: torch.Tensor,
        output_type: str = "pil",
    ) -> Union[List[Image.Image], torch.Tensor]:
        """Post-process decoded image.

        Args:
            image: Image tensor in range [0, 1]
            output_type: Output format ('pil' or 'np')

        Returns:
            PIL images or numpy array
        """
        if output_type == "pil":
            image = image.cpu().permute(0, 2, 3, 1).numpy()
            image = (image * 255).round().astype("uint8")
            return self.numpy_to_pil(image)
        elif output_type == "np":
            image = image.cpu().permute(0, 2, 3, 1).numpy()
            return image
        else:
            raise ValueError(f"Unknown output type: {output_type}")

    def encode_prompt(
        self,
        prompt: Union[str, List[str]],
        device: torch.device,
        num_images_per_prompt: int = 1,
        do_classifier_free_guidance: bool = True,
        negative_prompt: Optional[Union[str, List[str]]] = None,
    ) -> torch.Tensor:
        """Encode prompts with classifier-free guidance.

        Args:
            prompt: Text prompt(s)
            device: Device to use
            num_images_per_prompt: Number of images per prompt
            do_classifier_free_guidance: Whether to use classifier-free guidance
            negative_prompt: Negative prompt(s)

        Returns:
            Prompt embeddings
        """
        batch_size = 1 if isinstance(prompt, str) else len(prompt)

        text_input_ids = self.tokenizer(
            prompt,
            padding="max_length",
            truncation=True,
            max_length=self.tokenizer.model_max_length,
            return_tensors="pt",
        ).input_ids

        text_embeddings = self.text_encoder(text_input_ids.to(device))[0]

        if do_classifier_free_guidance:
            uncond_input = self.tokenizer(
                [""] * batch_size,
                padding="max_length",
                max_length=self.tokenizer.model_max_length,
                return_tensors="pt",
            )
            uncond_embeddings = self.text_encoder(uncond_input.input_ids.to(device))[0]
            text_embeddings = torch.cat([uncond_embeddings, text_embeddings])

        return text_embeddings
