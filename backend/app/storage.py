"""Safe paths for server-generated video and job identifiers."""

from pathlib import Path, PurePosixPath
from uuid import UUID

from .config import Settings


def video_dir(settings: Settings, video_id: UUID | str) -> Path:
    identifier = str(UUID(str(video_id)))
    return settings.data_dir / "videos" / identifier


def job_dir(settings: Settings, video_id: UUID | str, job_id: UUID | str) -> Path:
    identifier = str(UUID(str(job_id)))
    return video_dir(settings, video_id) / "jobs" / identifier


def relative_to_data(settings: Settings, path: Path) -> str:
    return path.resolve().relative_to(settings.data_dir.resolve()).as_posix()


def resolve_video_path(settings: Settings, video_id: UUID | str, stored_path: str) -> Path:
    """Resolve a stored data-root-relative path under its owning video."""
    relative = PurePosixPath(stored_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Invalid stored path")
    owner = video_dir(settings, video_id).resolve()
    candidate = (settings.data_dir / Path(*relative.parts)).resolve()
    if owner not in candidate.parents:
        raise ValueError("Stored path is outside its video directory")
    return candidate
