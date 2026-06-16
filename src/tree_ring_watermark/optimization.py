"""Optimization utilities for performance improvement.

This module provides utilities for optimizing model inference performance:
- torch.compile() support for faster execution
- Model quantization (bfloat16, int8)
- Memory optimization
- Benchmarking utilities
"""

import time
from typing import Callable, Optional, Tuple

import torch


def enable_torch_compile(model: torch.nn.Module, backend: str = "inductor") -> torch.nn.Module:
    """Enable torch.compile() optimization on a model.

    Args:
        model: PyTorch model to compile
        backend: Compilation backend (default: 'inductor')

    Returns:
        Compiled model, or original if compilation not available

    Note:
        torch.compile() requires PyTorch 2.0+ and may not work on all systems.
        CPU or older GPU architectures may not be supported.
    """
    if not hasattr(torch, "compile"):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("torch.compile() not available. Using standard execution.")
        return model

    try:
        compiled_model = torch.compile(model, backend=backend)
        return compiled_model
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to compile model: {e}. Using standard execution.")
        return model


def enable_memory_efficient_attention(
    model: torch.nn.Module,
    enable: bool = True,
) -> torch.nn.Module:
    """Enable memory-efficient attention implementations.

    Args:
        model: PyTorch model
        enable: Whether to enable (True) or disable (False)

    Returns:
        Model with memory-efficient attention enabled/disabled

    Note:
        Requires Flash Attention or similar implementation.
    """
    if enable and hasattr(torch.nn.functional, "scaled_dot_product_attention"):
        for module in model.modules():
            if hasattr(module, "attention"):
                module.attention.set_use_memory_efficient_attention_xformers(True)
    return model


def cast_to_dtype(
    model: torch.nn.Module,
    dtype: torch.dtype = torch.float16,
) -> torch.nn.Module:
    """Cast model to specified dtype for faster inference.

    Args:
        model: PyTorch model
        dtype: Target dtype (default: torch.float16 for bfloat16 use torch.bfloat16)

    Returns:
        Model cast to target dtype

    Note:
        Casting to float16 may cause numerical instability.
        bfloat16 is more stable but requires newer hardware.
    """
    return model.to(dtype)


def quantize_to_int8(model: torch.nn.Module) -> torch.nn.Module:
    """Quantize model to int8 for reduced memory and faster inference.

    Args:
        model: PyTorch model

    Returns:
        Quantized model

    Note:
        Requires pytorch quantization support.
        May require calibration for optimal performance.
    """
    try:
        quantized_model = torch.quantization.quantize_dynamic(
            model,
            {torch.nn.Linear},
            dtype=torch.qint8,
        )
        return quantized_model
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to quantize model: {e}. Using original model.")
        return model


def benchmark_function(
    func: Callable,
    *args,
    num_runs: int = 10,
    warmup_runs: int = 3,
    return_result: bool = False,
    **kwargs,
) -> Tuple[float, float, Optional[any]]:
    """Benchmark a function's execution time.

    Args:
        func: Function to benchmark
        *args: Positional arguments for function
        num_runs: Number of runs for timing (default: 10)
        warmup_runs: Number of warmup runs (default: 3)
        return_result: Whether to return function result
        **kwargs: Keyword arguments for function

    Returns:
        Tuple of (mean_time, std_time, result) where:
        - mean_time: Mean execution time in seconds
        - std_time: Standard deviation of execution time
        - result: Function result (only if return_result=True)
    """
    # Warmup runs
    for _ in range(warmup_runs):
        func(*args, **kwargs)

    # Timed runs
    times = []
    result = None
    for _ in range(num_runs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        times.append(end - start)

    import statistics
    mean_time = statistics.mean(times)
    std_time = statistics.stdev(times) if len(times) > 1 else 0.0

    if return_result:
        return mean_time, std_time, result
    else:
        return mean_time, std_time, None


def get_model_memory_footprint(model: torch.nn.Module) -> dict:
    """Calculate model memory footprint.

    Args:
        model: PyTorch model

    Returns:
        Dictionary with memory stats:
        - total_params: Total number of parameters
        - trainable_params: Trainable parameters
        - non_trainable_params: Frozen parameters
        - memory_mb: Approximate memory in MB (float32)
    """
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    non_trainable_params = total_params - trainable_params

    # Approximate memory in MB (4 bytes per float32 parameter)
    memory_mb = total_params * 4 / (1024 * 1024)

    return {
        "total_params": total_params,
        "trainable_params": trainable_params,
        "non_trainable_params": non_trainable_params,
        "memory_mb": memory_mb,
    }


class PerformanceMonitor:
    """Monitor and log performance metrics during execution."""

    def __init__(self, name: str = "Operation"):
        """Initialize performance monitor.

        Args:
            name: Name of operation being monitored
        """
        self.name = name
        self.start_time = None
        self.end_time = None
        self.elapsed_time = None

    def __enter__(self):
        """Enter context manager."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        self.end_time = time.perf_counter()
        self.elapsed_time = self.end_time - self.start_time

        if exc_type is None:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"{self.name} completed in {self.elapsed_time:.3f}s")

    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds.

        Returns:
            Elapsed time, or None if not yet finished
        """
        return self.elapsed_time
