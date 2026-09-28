"""Handoff between the durable worker and the ROB-3 video processor.

The processor writes derived files beneath ``work_dir`` and returns the manifest.
The worker validates and publishes those files; processors never change job state.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
from uuid import UUID

from .models.api import VideoManifest


@dataclass(frozen=True)
class ProcessingContext:
    video_id: UUID
    job_id: UUID
    source: Path
    work_dir: Path
    filename: str
    duration_seconds: float | None
    width: int | None
    height: int | None
    report_progress: Callable[[int], None]


class VideoProcessor(Protocol):
    def __call__(self, context: ProcessingContext) -> VideoManifest: ...


class ProcessingError(Exception):
    """A stable processing failure suitable for the job status response."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
