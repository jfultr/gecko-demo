"""SQLite source of truth for uploads and processing jobs."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import UUID


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS videos (
                    video_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    source_relpath TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    duration_seconds REAL,
                    width INTEGER,
                    height INTEGER
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL REFERENCES videos(video_id),
                    status TEXT NOT NULL CHECK(status IN ('queued','processing','completed','failed')),
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    progress_percent INTEGER CHECK(progress_percent BETWEEN 0 AND 100),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    error_retryable INTEGER,
                    result_relpath TEXT
                );
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status, created_at);
                CREATE INDEX IF NOT EXISTS jobs_video ON jobs(video_id);
            """)

    def create_video_and_job(
        self, *, video_id: UUID, job_id: UUID, filename: str,
        source_relpath: str, media_type: str, duration_seconds: float | None = None,
        width: int | None = None, height: int | None = None,
    ) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO videos VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(video_id), filename, source_relpath, media_type, now,
                 duration_seconds, width, height),
            )
            connection.execute(
                "INSERT INTO jobs (job_id, video_id, status, created_at, updated_at) "
                "VALUES (?, ?, 'queued', ?, ?)",
                (str(job_id), str(video_id), now, now),
            )

    def get_video(self, video_id: UUID | str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM videos WHERE video_id = ?", (str(video_id),)
            ).fetchone()

    def get_job(self, job_id: UUID | str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (str(job_id),)
            ).fetchone()

    def get_video_job(self, video_id: UUID | str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM jobs WHERE video_id = ? ORDER BY created_at DESC LIMIT 1",
                (str(video_id),),
            ).fetchone()

    def claim_next_job(self) -> sqlite3.Row | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            job = connection.execute(
                "SELECT job_id FROM jobs WHERE status = 'queued' "
                "ORDER BY created_at, job_id LIMIT 1"
            ).fetchone()
            if job is None:
                return None
            connection.execute(
                "UPDATE jobs SET status = 'processing', attempt_count = attempt_count + 1, "
                "started_at = ?, updated_at = ?, progress_percent = NULL WHERE job_id = ?",
                (utc_now(), utc_now(), job["job_id"]),
            )
            return connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job["job_id"],)
            ).fetchone()

    def set_progress(self, job_id: UUID | str, percent: int | None) -> None:
        if percent is not None and not 0 <= percent <= 100:
            raise ValueError("Progress must be between 0 and 100")
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET progress_percent = ?, updated_at = ? "
                "WHERE job_id = ? AND status = 'processing'",
                (percent, utc_now(), str(job_id)),
            )

    def complete_job(self, job_id: UUID | str, result_relpath: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE jobs SET status = 'completed', progress_percent = 100, "
                "result_relpath = ?, finished_at = ?, updated_at = ?, "
                "error_code = NULL, error_message = NULL, error_retryable = NULL "
                "WHERE job_id = ? AND status = 'processing'",
                (result_relpath, now, now, str(job_id)),
            )
            if cursor.rowcount != 1:
                raise ValueError("Job is not processing")

    def fail_job(self, job_id: UUID | str, code: str, message: str, retryable: bool = False) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'failed', progress_percent = NULL, "
                "result_relpath = NULL, error_code = ?, error_message = ?, "
                "error_retryable = ?, finished_at = ?, updated_at = ? "
                "WHERE job_id = ? AND status IN ('queued', 'processing', 'completed')",
                (code, message, int(retryable), now, now, str(job_id)),
            )

    def reconcile_interrupted(self) -> list[sqlite3.Row]:
        """Reset interrupted work once and return affected rows for disk cleanup."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            jobs = connection.execute(
                "SELECT * FROM jobs WHERE status = 'processing'"
            ).fetchall()
            for job in jobs:
                if job["attempt_count"] >= 2:
                    connection.execute(
                        "UPDATE jobs SET status = 'failed', progress_percent = NULL, "
                        "error_code = 'WORKER_INTERRUPTED', "
                        "error_message = 'Processing was interrupted twice.', "
                        "error_retryable = 0, finished_at = ?, updated_at = ? "
                        "WHERE job_id = ?",
                        (utc_now(), utc_now(), job["job_id"]),
                    )
                else:
                    connection.execute(
                        "UPDATE jobs SET status = 'queued', progress_percent = NULL, "
                        "started_at = NULL, error_code = NULL, error_message = NULL, "
                        "error_retryable = NULL, updated_at = ? WHERE job_id = ?",
                        (utc_now(), job["job_id"]),
                    )
            return jobs
