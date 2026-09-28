"""Identify supported video containers and inspect their video streams."""

import json
from pathlib import Path
import subprocess


class UnsupportedVideoFormat(ValueError):
    pass


class InvalidVideo(ValueError):
    pass


class ProbeUnavailable(RuntimeError):
    pass


_FORMATS = {
    ".mp4": ("video/mp4", "mp4"),
    ".mov": ("video/quicktime", "mov"),
    ".webm": ("video/webm", "webm"),
}


def inspect_video(path: Path, filename: str, claimed_type: str | None) -> tuple[str, str, float, int, int]:
    """Return canonical MIME, extension, duration, width and height."""
    suffix = Path(filename).suffix.lower()
    if suffix not in _FORMATS:
        raise UnsupportedVideoFormat("Supported video formats are MP4, MOV and WebM.")
    media_type, container = _FORMATS[suffix]
    claimed = (claimed_type or "").split(";", 1)[0].strip().lower()
    if claimed not in ("", "application/octet-stream", media_type):
        raise UnsupportedVideoFormat("The uploaded media type does not match its format.")

    with path.open("rb") as source:
        header = source.read(64)
    if container == "webm":
        if not header.startswith(b"\x1a\x45\xdf\xa3"):
            raise UnsupportedVideoFormat("The file is not a WebM video.")
    elif len(header) < 12 or header[4:8] != b"ftyp":
        raise UnsupportedVideoFormat("The file is not an MP4 or MOV video.")

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,format_name:stream=codec_type,width,height,duration", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        raise ProbeUnavailable("Video inspection is temporarily unavailable.") from exc
    if result.returncode != 0:
        raise InvalidVideo("The video could not be read.")
    try:
        details = json.loads(result.stdout)
        format_names = set(details["format"]["format_name"].split(","))
        expected = "matroska" if container == "webm" else "mov"
        if expected not in format_names:
            raise UnsupportedVideoFormat("The video container does not match its extension.")
        streams = [stream for stream in details["streams"] if stream.get("codec_type") == "video"]
        if not streams:
            raise InvalidVideo("The file has no video stream.")
        stream = streams[0]
        duration = float(details["format"].get("duration") or stream["duration"])
        width, height = int(stream["width"]), int(stream["height"])
        if duration <= 0 or width <= 0 or height <= 0:
            raise ValueError("Invalid video dimensions or duration")
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise InvalidVideo("The video has invalid metadata.") from exc
    return media_type, suffix, duration, width, height
