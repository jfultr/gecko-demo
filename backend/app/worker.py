"""Single local worker backed by SQLite. Run from backend: python -m app.worker.

Configure APP_DATA_DIR and APP_PROCESSOR=package.module:function. The callable
accepts ProcessingContext and returns VideoManifest. See app.processing.
"""

import argparse
import importlib
import logging
import os
from pathlib import Path
import re
import shutil
import sys
import time
from uuid import UUID

from .config import Settings
from .db import Database
from .models.api import VideoManifest
from .processing import ProcessingContext, ProcessingError, VideoProcessor
from .storage import job_dir, relative_to_data, resolve_video_path


LOG = logging.getLogger(__name__)
FRAME_ID = re.compile(r"frame-[0-9]{6,}\Z")
STALE_UPLOAD_SECONDS = 24 * 60 * 60


def load_processor(spec: str) -> VideoProcessor:
    """Import the ROB-3 processor before claiming any queued job."""
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("APP_PROCESSOR must be package.module:function")
    processor = getattr(importlib.import_module(module_name), attribute)
    if not callable(processor):
        raise TypeError("APP_PROCESSOR must resolve to a callable")
    return processor


def _safe_remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _validate_result(manifest: VideoManifest, video_id: UUID, source: Path, work: Path) -> None:
    if manifest.video.video_id != video_id:
        raise ProcessingError("PROCESSING_FAILED", "The result belongs to another video.")
    if manifest.video.source_url != f"/api/v1/videos/{video_id}/source":
        raise ProcessingError("PROCESSING_FAILED", "The result has an invalid source URL.")
    if not source.is_file() or source.stat().st_size == 0:
        raise ProcessingError("SOURCE_MISSING", "The source video is missing.")
    for filename in ("scores.v1.json", "embeddings/vectors.npz", "embeddings/metadata.json"):
        asset = work / filename
        if not asset.is_file() or asset.stat().st_size == 0:
            raise ProcessingError("PROCESSING_FAILED", "The processor returned an incomplete result.")
    for peak in manifest.peaks:
        frame = peak.frame
        if not FRAME_ID.fullmatch(frame.frame_id):
            raise ProcessingError("PROCESSING_FAILED", "The result has an invalid frame ID.")
        expected = f"/api/v1/videos/{video_id}/frames/{frame.frame_id}"
        image = work / "frames" / f"{frame.frame_id}.jpg"
        if frame.image_url != expected or not image.is_file() or image.stat().st_size == 0:
            raise ProcessingError("PROCESSING_FAILED", "The result has a missing evidence frame.")


def _inspect_published(db: Database, settings: Settings) -> None:
    """Invalidate completed rows with missing or mismatched published assets."""
    with db.connect() as connection:
        rows = connection.execute("SELECT * FROM jobs WHERE status = 'completed'").fetchall()
    for job in rows:
        try:
            video_id = UUID(job["video_id"])
            video = db.get_video(video_id)
            if video is None or not job["result_relpath"]:
                raise ValueError("Missing video or result path")
            source = resolve_video_path(settings, video_id, video["source_relpath"])
            manifest_path = resolve_video_path(settings, video_id, job["result_relpath"])
            expected = job_dir(settings, video_id, job["job_id"]) / "result" / "manifest.v1.json"
            if manifest_path != expected.resolve():
                raise ValueError("Unexpected result path")
            manifest = VideoManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
            _validate_result(manifest, video_id, source, manifest_path.parent)
        except (OSError, ValueError, ProcessingError) as exc:
            LOG.error("Published assets failed integrity check for job %s: %s", job["job_id"], exc)
            db.fail_job(job["job_id"], "STORAGE_ERROR", "Published result assets are unavailable.")


def reconcile_startup(db: Database, settings: Settings) -> None:
    for job in db.reconcile_interrupted():
        directory = job_dir(settings, job["video_id"], job["job_id"])
        _safe_remove(directory / "work")
        _safe_remove(directory / "result")
    with db.connect() as connection:
        jobs = connection.execute("SELECT * FROM jobs").fetchall()
    for job in jobs:
        # The worker lock guarantees no live processing attempt owns this directory.
        _safe_remove(job_dir(settings, job["video_id"], job["job_id"]) / "work")
        if job["status"] != "queued":
            continue
        video = db.get_video(job["video_id"])
        try:
            if video is None or not resolve_video_path(settings, job["video_id"], video["source_relpath"]).is_file():
                raise FileNotFoundError
        except (ValueError, FileNotFoundError):
            db.fail_job(job["job_id"], "SOURCE_MISSING", "The source video is missing.")
    _inspect_published(db, settings)
    cutoff = time.time() - STALE_UPLOAD_SECONDS
    for path in (settings.data_dir / "staging").glob("*.part"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            _safe_remove(path)


def process_one(db: Database, settings: Settings, processor: VideoProcessor) -> bool:
    job = db.claim_next_job()
    if job is None:
        return False
    video_id = UUID(job["video_id"])
    job_id = UUID(job["job_id"])
    directory = job_dir(settings, video_id, job_id)
    work = directory / "work"
    result = directory / "result"
    try:
        video = db.get_video(video_id)
        if video is None:
            raise ProcessingError("SOURCE_MISSING", "The source video is missing.")
        source = resolve_video_path(settings, video_id, video["source_relpath"])
        if not source.is_file():
            raise ProcessingError("SOURCE_MISSING", "The source video is missing.")
        _safe_remove(work)
        # A result without a completed row is an orphan from interrupted publication.
        _safe_remove(result)
        work.mkdir(parents=True)
        context = ProcessingContext(
            video_id=video_id, job_id=job_id, source=source, work_dir=work,
            filename=video["filename"], duration_seconds=video["duration_seconds"],
            width=video["width"], height=video["height"],
            report_progress=lambda percent: db.set_progress(job_id, percent),
        )
        manifest = processor(context)
        if not isinstance(manifest, VideoManifest):
            manifest = VideoManifest.model_validate(manifest)
        _validate_result(manifest, video_id, source, work)
        manifest_path = work / "manifest.v1.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        os.replace(work, result)
        db.complete_job(job_id, relative_to_data(settings, result / "manifest.v1.json"))
        LOG.info("Completed job %s", job_id)
    except ProcessingError as exc:
        LOG.warning("Job %s failed: %s", job_id, exc)
        db.fail_job(job_id, exc.code, str(exc), retryable=exc.retryable)
    except Exception:
        LOG.exception("Job %s failed", job_id)
        db.fail_job(job_id, "PROCESSING_FAILED", "The video could not be processed.")
    finally:
        _safe_remove(work)
        if db.get_job(job_id)["status"] != "completed":
            _safe_remove(result)
    return True


def run(settings: Settings, processor: VideoProcessor, poll_seconds: float = 1.0) -> None:
    if poll_seconds <= 0:
        raise ValueError("Polling interval must be positive")
    settings.prepare()
    db = Database(settings.database_path)
    db.initialize()
    # One lock owner performs reconciliation and processing. The DB transaction
    # still makes claims atomic if another consumer is introduced later.
    lock_file = (settings.data_dir / "worker.lock").open("a+b")
    try:
        if sys.platform == "win32":
            import msvcrt
            lock_file.seek(0)
            lock_file.write(b"0")
            lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        reconcile_startup(db, settings)
        while True:
            if not process_one(db, settings, processor):
                time.sleep(poll_seconds)
    finally:
        lock_file.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Gecko video processing worker")
    parser.add_argument("--processor", default=os.environ.get("APP_PROCESSOR"),
                        help="ROB-3 callable as package.module:function (or APP_PROCESSOR)")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    if not args.processor:
        parser.error("--processor or APP_PROCESSOR is required until ROB-3 is integrated")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run(Settings.from_env(), load_processor(args.processor), args.poll_seconds)
    except BlockingIOError as exc:
        raise SystemExit("Another worker already owns APP_DATA_DIR") from exc


if __name__ == "__main__":
    main()
