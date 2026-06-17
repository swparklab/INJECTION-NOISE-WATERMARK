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


def probe_fps(path: str | Path, default: float = 30.0) -> float:
    """Return the video's frame rate, falling back to ``default`` if unknown."""
    try:
        import imageio.v3 as iio

        meta = iio.immeta(str(path), plugin="pyav")
        fps = meta.get("fps")
        return float(fps) if fps else default
    except Exception:
        return default


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
    crf: int = 16,
    preset: str = "slow",
    output_params: list[str] | None = None,
) -> None:
    """Write RGB frames to a video file.

    Args:
        path: Output path.
        frames: List of RGB frames.
        fps: Frames per second.
        codec: FFmpeg codec (``libx264`` = H.264, ``libx265`` = H.265).
        crf: Constant rate factor. Lower = higher quality. The watermark is a
            low-amplitude high-frequency signal, so a high-quality encode
            (``crf<=16``) is required for it to survive the *embedding* encode;
            the default 23 used by most tools destroys it.
        preset: x264 speed/quality preset.
        output_params: Explicit FFmpeg output params (overrides crf/preset).
    """
    import imageio.v2 as iio

    if output_params is None:
        output_params = ["-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p"]
    with iio.get_writer(
        str(path),
        fps=fps,
        codec=codec,
        macro_block_size=None,
        output_params=output_params,
    ) as writer:
        for frame in frames:
            writer.append_data(frame)
