"""Video frame I/O helpers.

Reads/writes video frames as RGB ``np.ndarray`` using imageio (FFmpeg backend).
Used by the video embed/detect/trace flows. Designed to stream frames so large
files do not need to fit in memory.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np


def read_frames(path: str | Path, max_frames: int | None = None) -> Iterator[np.ndarray]:
    """Yield RGB frames from a video file.

    Args:
        path: Path to the video file.
        max_frames: Optional cap on the number of frames yielded.

    Yields:
        RGB frames as uint8 ``np.ndarray`` of shape (H, W, 3).
    """
    import imageio.v3 as iio

    count = 0
    for frame in iio.imiter(str(path)):
        if frame.ndim == 2:
            frame = np.stack([frame] * 3, axis=-1)
        if frame.shape[-1] == 4:
            frame = frame[..., :3]
        yield frame.astype(np.uint8)
        count += 1
        if max_frames is not None and count >= max_frames:
            break


def sample_frames(path: str | Path, n: int = 16) -> list[np.ndarray]:
    """Read up to ``n`` evenly-spaced frames for detection/tracing.

    Args:
        path: Path to the video file.
        n: Number of frames to sample.

    Returns:
        List of sampled RGB frames.
    """
    frames = list(read_frames(path))
    if not frames:
        return []
    if len(frames) <= n:
        return frames
    idx = np.linspace(0, len(frames) - 1, n).astype(int)
    return [frames[i] for i in idx]


def write_frames(
    path: str | Path,
    frames: list[np.ndarray],
    fps: float = 30.0,
    codec: str = "libx264",
    quality: int | None = None,
) -> None:
    """Write RGB frames to a video file.

    Args:
        path: Output path.
        frames: List of RGB frames.
        fps: Frames per second.
        codec: FFmpeg codec (``libx264`` = H.264, ``libx265`` = H.265).
        quality: Optional CRF-like quality hint.
    """
    import imageio.v2 as iio

    writer_kwargs = {"fps": fps, "codec": codec, "macro_block_size": None}
    if quality is not None:
        writer_kwargs["quality"] = quality
    with iio.get_writer(str(path), **writer_kwargs) as writer:
        for frame in frames:
            writer.append_data(frame)
