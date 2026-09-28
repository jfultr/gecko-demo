"""Pydantic models shared by the Gecko Demo API and its clients.

These models describe the v1 JSON contract. The API prefix is ``/api/v1``;
``schema_version`` on manifests lets fixtures and saved results evolve safely.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Base model with strict handling of unexpected contract fields."""

    model_config = ConfigDict(extra="forbid")


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ErrorDetail(ApiModel):
    code: str = Field(description="Stable machine-readable error code.")
    message: str
    retryable: bool = False


class ErrorResponse(ApiModel):
    error: ErrorDetail


class VideoUploadResponse(ApiModel):
    """Response after the source video has been accepted for processing."""

    video_id: UUID
    job_id: UUID
    status: JobStatus = JobStatus.QUEUED


class JobResponse(ApiModel):
    job_id: UUID
    video_id: UUID
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    # Present while processing; 0–100, and omitted when progress is unknown.
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    error: ErrorDetail | None = None
    # Set when status is completed; points to GET /api/v1/videos/{video_id}/manifest.
    manifest_url: str | None = None


class VideoInfo(ApiModel):
    video_id: UUID
    filename: str
    source_url: str = Field(description="URL or API-relative path for video playback.")
    duration_seconds: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class RiskSample(ApiModel):
    """Semantic similarity score at a timestamp, not a safety decision."""

    timestamp_seconds: float = Field(ge=0)
    score: float = Field(ge=0, le=100)


class EvidenceFrame(ApiModel):
    frame_id: str
    timestamp_seconds: float = Field(ge=0)
    image_url: str = Field(
        description="URL or API-relative path for the extracted evidence frame."
    )


class PeakEvent(ApiModel):
    event_id: str
    timestamp_seconds: float = Field(ge=0)
    score: float = Field(ge=0, le=100)
    level: RiskLevel
    frame: EvidenceFrame
    prompt: str = Field(description="Prompt that contributed to this score.")


class PromptPreset(ApiModel):
    preset_id: str
    label: str
    positive_prompts: list[str] = Field(min_length=1)
    negative_prompts: list[str] = Field(default_factory=list)


class VideoManifest(ApiModel):
    """Processed-video data consumed by the player and peak navigator."""

    schema_version: Literal["1.0"] = "1.0"
    video: VideoInfo
    generated_at: datetime
    score_label: Literal["semantic_similarity"] = "semantic_similarity"
    score_range: tuple[Literal[0], Literal[100]] = (0, 100)
    preset: PromptPreset
    samples: list[RiskSample]
    peaks: list[PeakEvent]


__all__ = [
    "ApiModel",
    "ErrorDetail",
    "ErrorResponse",
    "EvidenceFrame",
    "JobResponse",
    "JobStatus",
    "PeakEvent",
    "PromptPreset",
    "RiskLevel",
    "RiskSample",
    "VideoInfo",
    "VideoManifest",
    "VideoUploadResponse",
]
