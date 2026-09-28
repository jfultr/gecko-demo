"""Durable job status endpoint."""

from fastapi import APIRouter, Request

from ..errors import api_error
from ..models.api import ErrorDetail, JobResponse, JobStatus


router = APIRouter(prefix="/api/v1")


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, request: Request) -> JobResponse:
    job = request.app.state.database.get_job(job_id)
    if job is None:
        raise api_error(404, "NOT_FOUND", "Job not found.")

    status = JobStatus(job["status"])
    error = None
    manifest_url = None
    if status is JobStatus.FAILED:
        error = ErrorDetail(
            code=job["error_code"] or "PROCESSING_FAILED",
            message=job["error_message"] or "The video could not be processed.",
            retryable=bool(job["error_retryable"]),
        )
    elif status is JobStatus.COMPLETED:
        manifest_url = f'/api/v1/videos/{job["video_id"]}/manifest'

    return JobResponse(
        job_id=job["job_id"],
        video_id=job["video_id"],
        status=status,
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        progress_percent=job["progress_percent"],
        error=error,
        manifest_url=manifest_url,
    )
