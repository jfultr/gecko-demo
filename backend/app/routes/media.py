"""Manifest and media routes for persisted video results."""

from pathlib import Path
import re
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import ValidationError

from ..errors import api_error
from ..models.api import VideoManifest
from ..storage import job_dir, resolve_video_path


router = APIRouter(prefix="/api/v1/videos", tags=["videos"])
_RANGE = re.compile(r"bytes=(\d*)-(\d*)\Z")


def _video(request: Request, video_id: str):
    try:
        identifier = UUID(video_id)
    except ValueError:
        raise api_error(404, "NOT_FOUND", "Video not found.") from None
    video = request.app.state.database.get_video(identifier)
    if video is None:
        raise api_error(404, "NOT_FOUND", "Video not found.")
    return video


def _result_job(request: Request, video_id: str):
    job = request.app.state.database.get_video_job(video_id)
    if job is None:
        raise api_error(404, "NOT_FOUND", "Video not found.")
    if job["status"] == "failed":
        raise api_error(409, "JOB_FAILED", "The video could not be processed.")
    if job["status"] != "completed":
        raise api_error(409, "JOB_NOT_COMPLETE", "The video is still processing.", True)
    return job


def _storage_failure(request: Request, job, message: str):
    request.app.state.database.fail_job(job["job_id"], "STORAGE_ERROR", message)
    raise api_error(409, "JOB_FAILED", "The processed result is unavailable.")


def _frame_file(manifest_path: Path, frame_id: str) -> Path:
    result_dir = manifest_path.parent.resolve()
    frames_dir = (result_dir / "frames").resolve()
    frame = (frames_dir / f"{frame_id}.jpg").resolve()
    if frames_dir.parent != result_dir or frame.parent != frames_dir:
        raise ValueError("Evidence frame path escapes the result directory")
    return frame


def _manifest(request: Request, video_id: str, video, job) -> tuple[VideoManifest, Path]:
    stored_path = job["result_relpath"]
    if not stored_path:
        _storage_failure(request, job, "The result manifest path is missing.")
    try:
        path = resolve_video_path(request.app.state.settings, video_id, stored_path)
        expected_path = job_dir(
            request.app.state.settings, video_id, job["job_id"]
        ) / "result" / "manifest.v1.json"
        if path != expected_path.resolve():
            raise ValueError("Unexpected result manifest path")
        manifest = VideoManifest.model_validate_json(path.read_bytes())
        if manifest.video.video_id != UUID(video_id):
            raise ValueError("Manifest video ID does not match")
        source_url = f"/api/v1/videos/{video_id}/source"
        if manifest.video.source_url != source_url:
            raise ValueError("Manifest source URL does not match")
        source = resolve_video_path(
            request.app.state.settings, video_id, video["source_relpath"]
        )
        if not source.is_file():
            raise FileNotFoundError("Source video is missing")
        for peak in manifest.peaks:
            frame_id = peak.frame.frame_id
            expected = f"/api/v1/videos/{video_id}/frames/{frame_id}"
            if peak.frame.image_url != expected or not re.fullmatch(r"frame-[0-9]{6,}", frame_id):
                raise ValueError("Manifest frame reference is invalid")
            if not _frame_file(path, frame_id).is_file():
                raise FileNotFoundError("Evidence frame is missing")
    except (OSError, ValueError, ValidationError):
        _storage_failure(request, job, "The published result failed an integrity check.")
    return manifest, path


@router.get("/{video_id}/manifest", response_model=VideoManifest)
def get_manifest(video_id: str, request: Request) -> VideoManifest:
    video = _video(request, video_id)
    canonical_id = video["video_id"]
    job = _result_job(request, canonical_id)
    manifest, _ = _manifest(request, canonical_id, video, job)
    return manifest


def _range_bounds(header: str | None, size: int) -> tuple[int, int] | None:
    if header is None:
        return None
    match = _RANGE.fullmatch(header.strip())
    if match is None or (not match.group(1) and not match.group(2)):
        raise ValueError("Invalid byte range")
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if suffix == 0:
            raise ValueError("Invalid suffix range")
        return max(0, size - suffix), size - 1
    start = int(first)
    end = int(last) if last else size - 1
    if start >= size or end < start:
        raise ValueError("Unsatisfiable byte range")
    return start, min(end, size - 1)


def _file_chunks(path: Path, start: int, end: int):
    with path.open("rb") as source:
        source.seek(start)
        remaining = end - start + 1
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/{video_id}/source")
def get_source(video_id: str, request: Request):
    video = _video(request, video_id)
    try:
        source = resolve_video_path(
            request.app.state.settings, video["video_id"], video["source_relpath"]
        )
        size = source.stat().st_size
        if not source.is_file() or size == 0:
            raise OSError("Source video is missing")
    except (OSError, ValueError):
        job = request.app.state.database.get_video_job(video["video_id"])
        if job is not None:
            request.app.state.database.fail_job(
                job["job_id"], "STORAGE_ERROR", "The source video is missing."
            )
        raise api_error(500, "INTERNAL_ERROR", "The source video is unavailable.") from None

    try:
        bounds = _range_bounds(request.headers.get("range"), size)
    except ValueError:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=416,
            content={"error": {"code": "INVALID_REQUEST", "message": "Invalid byte range.", "retryable": False}},
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )
    start, end = bounds if bounds is not None else (0, size - 1)
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(end - start + 1)}
    if bounds is not None:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(
        _file_chunks(source, start, end),
        status_code=206 if bounds is not None else 200,
        media_type=video["media_type"],
        headers=headers,
    )


@router.get("/{video_id}/frames/{frame_id}")
def get_frame(video_id: str, frame_id: str, request: Request):
    video = _video(request, video_id)
    canonical_id = video["video_id"]
    job = _result_job(request, canonical_id)
    manifest, path = _manifest(request, canonical_id, video, job)
    if frame_id not in {peak.frame.frame_id for peak in manifest.peaks}:
        raise api_error(404, "NOT_FOUND", "Frame not found.")
    frame = _frame_file(path, frame_id)
    if not frame.is_file():
        _storage_failure(request, job, "An evidence frame is missing.")
    return FileResponse(frame, media_type="image/jpeg")
