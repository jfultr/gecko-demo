"""Validated source-video upload and durable job creation."""

import asyncio
from pathlib import Path
import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from ..media_probe import InvalidVideo, ProbeUnavailable, UnsupportedVideoFormat, inspect_video
from ..models.api import ErrorDetail, ErrorResponse, VideoUploadResponse
from ..storage import relative_to_data, video_dir


router = APIRouter()
_CHUNK_BYTES = 1024 * 1024


def _error(status_code: int, code: str, message: str, retryable: bool = False) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, retryable=retryable))
    return JSONResponse(status_code=status_code, content=body.model_dump())


@router.post("/api/v1/videos", status_code=202, response_model=VideoUploadResponse,
             responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse},
                        415: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
                        500: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
async def upload_video(request: Request):
    settings = request.app.state.settings
    database = request.app.state.database
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        return _error(400, "INVALID_REQUEST", "Expected multipart/form-data with one file.")

    try:
        async with request.form() as form:
            if list(form.keys()) != ["file"] or len(form.getlist("file")) != 1:
                return _error(400, "INVALID_REQUEST", "Expected exactly one file part.")
            upload = form["file"]
            if not isinstance(upload, UploadFile) or not upload.filename:
                return _error(400, "INVALID_REQUEST", "The file part must have a filename.")

            video_id, job_id = uuid4(), uuid4()
            stage = settings.data_dir / "staging" / f"{uuid4()}.part"
            destination: Path | None = None
            accepted = False
            try:
                size = 0
                with stage.open("xb") as output:
                    while chunk := await upload.read(_CHUNK_BYTES):
                        size += len(chunk)
                        if size > settings.max_upload_bytes:
                            return _error(413, "FILE_TOO_LARGE", "The video exceeds the upload limit.")
                        output.write(chunk)
                if size == 0:
                    return _error(422, "INVALID_VIDEO", "The video is empty.")

                try:
                    media_type, extension, duration, width, height = await asyncio.to_thread(
                        inspect_video, stage, upload.filename, upload.content_type
                    )
                except UnsupportedVideoFormat as exc:
                    return _error(415, "UNSUPPORTED_VIDEO_FORMAT", str(exc))
                except InvalidVideo as exc:
                    return _error(422, "INVALID_VIDEO", str(exc))
                except ProbeUnavailable as exc:
                    return _error(503, "SERVICE_UNAVAILABLE", str(exc), retryable=True)

                destination = video_dir(settings, video_id) / "source" / f"original{extension}"
                destination.parent.mkdir(parents=True, exist_ok=False)
                os.replace(stage, destination)
                response = VideoUploadResponse(video_id=video_id, job_id=job_id)
                database.create_video_and_job(
                    video_id=video_id,
                    job_id=job_id,
                    filename=upload.filename,
                    source_relpath=relative_to_data(settings, destination),
                    media_type=media_type,
                    duration_seconds=duration,
                    width=width,
                    height=height,
                )
                accepted = True
                return response
            except OSError:
                return _error(503, "SERVICE_UNAVAILABLE", "The upload could not be stored.", retryable=True)
            except Exception:
                return _error(500, "INTERNAL_ERROR", "The upload could not be accepted.")
            finally:
                stage.unlink(missing_ok=True)
                if not accepted and destination is not None:
                    shutil.rmtree(video_dir(settings, video_id), ignore_errors=True)
    except Exception:
        return _error(400, "INVALID_REQUEST", "The multipart upload is malformed.")
