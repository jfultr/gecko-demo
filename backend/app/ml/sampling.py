"""Deterministic midpoint sampling using decoded video-frame timestamps."""

import math
from pathlib import Path
import subprocess

from ..processing import ProcessingError


MAX_FRAMES = 180


def midpoint_targets(duration: float) -> list[float]:
    if not math.isfinite(duration) or duration <= 0:
        raise ProcessingError("INVALID_VIDEO", "Video duration must be positive.")
    count = min(MAX_FRAMES, max(1, math.ceil(duration)))
    return [duration * (index + 0.5) / count for index in range(count)]


def sampled_timestamps(source: Path, duration: float) -> list[float]:
    """Choose the nearest real decoded frame to each midpoint; deduplicate sparse video."""
    targets = midpoint_targets(duration)
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "frame=best_effort_timestamp_time", "-of", "csv=p=0",
             str(source)],
            capture_output=True, text=True, timeout=600, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProcessingError("VIDEO_DECODE_FAILED", "Video frame inspection failed.") from exc
    if result.returncode != 0:
        raise ProcessingError("VIDEO_DECODE_FAILED", "Video frames could not be inspected.")
    timestamps = []
    for line in result.stdout.splitlines():
        try:
            value = float(line.split(",", 1)[0])
        except ValueError:
            continue
        if math.isfinite(value) and value >= 0 and (not timestamps or value > timestamps[-1]):
            timestamps.append(value)
    if not timestamps:
        raise ProcessingError("VIDEO_DECODE_FAILED", "The video contains no decoded frames.")
    selected = []
    cursor = 0
    for target in targets:
        while cursor + 1 < len(timestamps) and abs(timestamps[cursor + 1] - target) < abs(timestamps[cursor] - target):
            cursor += 1
        value = timestamps[cursor]
        if not selected or value > selected[-1]:
            selected.append(value)
    return selected


def extract_frame(source: Path, timestamp: float, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
             "-i", str(source), "-ss", f"{max(0, timestamp - 0.000001):.9f}",
             "-map", "0:v:0", "-frames:v", "1", "-q:v", "2", str(destination)],
            capture_output=True, text=True, timeout=120, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProcessingError("VIDEO_DECODE_FAILED", "The sampled frame could not be decoded.") from exc
    if result.returncode != 0 or not destination.is_file() or destination.stat().st_size == 0:
        raise ProcessingError("VIDEO_DECODE_FAILED", "The sampled frame could not be decoded.")
