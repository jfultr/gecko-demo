# Local storage and processing jobs (ROB-13)

This is the MVP storage contract for a single local backend process and one worker.
The HTTP response shapes are defined in `backend/app/models/api.py`. Paths in this
document are internal implementation details and must never be returned to a client.

## Ownership and on-disk layout

Configure an absolute `APP_DATA_DIR` outside the repository. The backend creates and
owns this directory; the worker only writes below it. Do not serve it as a static
directory. Resolve video and job paths from server-generated UUIDs, never from an
uploaded filename or a request path.

```text
APP_DATA_DIR/
  gecko.sqlite3
  staging/
    <upload-id>.part
  videos/
    <video-id>/
      source/
        original.<validated-extension>
      jobs/
        <job-id>/
          work/                    # disposable, private to this attempt
          result/
            manifest.v1.json      # published only after completion
            scores.v1.json        # full time series used to build the manifest
            frames/
              <frame-id>.jpg
            clips/                # optional derived clips
              <clip-id>.mp4
            embeddings/           # implementation format + model metadata
```

The raw source is immutable after the upload is accepted. Files in `result/` are
derived from that source and may be regenerated. The manifest is the frontend's
versioned view of a completed result, with `schema_version: "1.0"`. `scores.v1.json`
holds the canonical series for processing/rebuilds; the manifest copies the samples
needed by the player. Evidence frames and optional clips are separate media files.
Embeddings are separate from scores and the manifest because their format and
retention can change with the model. Record the embedding model identifier and
version beside any retained vectors. ROB-14 will settle whether completed embeddings
are retained or discarded after manifest publication.

Use a temporary upload in `staging/` and an atomic move into `source/` before
committing a queued job. Build all derived files in `work/`; validate the final
manifest with `VideoManifest`, then atomically promote a complete result and mark
the job completed. A client must never observe a partially written manifest.

## Durable metadata

Use SQLite at `APP_DATA_DIR/gecko.sqlite3` with WAL mode. It is the authority for
video and job identity and status; files hold large media and result payloads.
The minimum records are:

| Record | Fields | Purpose |
| --- | --- | --- |
| `videos` | `video_id` (UUID primary key), original filename, safe source relative path, upload time, media probe fields (duration, width, height) | Maps a public video ID to its immutable source. The original filename is display metadata only. |
| `jobs` | `job_id` (UUID primary key), `video_id` (foreign key), status, progress percent (nullable), created/updated times, started/finished times (nullable), error code/message/retryable (nullable), result relative path (nullable) | Persists processing state and the published result. For the MVP, one upload creates one video and one job. |

All timestamps are UTC. Store relative paths only and join them to the configured
data root after validating that the resolved path remains inside the expected video
directory. The database stores the active job for a video (or the video row points to
it); `GET /api/v1/videos/{video_id}/manifest` resolves to that job's published
manifest. Frame and source URLs in `VideoManifest` are API routes, not filesystem
paths. The API streams those assets after checking the video/job relationship.

`video_id` and `job_id` use UUIDs matching `VideoUploadResponse`, `JobResponse`, and
`VideoInfo`. `frame_id` and `event_id` are stable within a published result. Generate
them deterministically from the ordered sample/peak index (for example,
`frame-000123`), so rebuilding the same ordered result does not change links.
Do not use timestamps alone as IDs: rounding or duplicate timestamps can collide.

## Job state and recovery

```text
queued -> processing -> completed
                     -> failed
completed -> failed (only if published assets fail an integrity check)
```

Only these four public statuses are valid. A newly accepted upload is `queued`.
The worker claims one queued job transactionally, changing it to `processing` and
setting `started_at`. Progress is optional and stays within 0–100. On success,
publish the validated result first, then commit `completed`, `finished_at`, and its
result path in one database transaction. A completed job has a manifest URL; a failed
job has an `ErrorDetail`. A terminal job is never changed back to `processing`.
The exceptional `completed -> failed` transition prevents a corrupt published
result from remaining available after an integrity check fails.

At startup, the worker reconciles the database and disk:

1. Any job left in `processing` after an interrupted run returns to `queued`, clears
   its progress and transient error, and removes its unpromoted `work/` directory.
   Reprocessing the same job ID must be safe.
2. A queued job whose source file is missing becomes `failed` with a stable
   non-retryable error code. A published result without a matching completed database
   record is not exposed; recovery can either validate and publish it or remove it
   before retrying.
3. A completed job whose manifest or referenced media is missing becomes `failed`
   with a storage error rather than serving an incomplete result.

Job status is durable across API and worker restarts; the in-memory queue is only a
wakeup mechanism. Polling `jobs` for queued records is sufficient for the MVP.
Updates to status and progress must include `updated_at` so polling clients can
observe changes. The backend should not report `completed` until the manifest and
all referenced assets are readable.

## Cleanup and deletion

Remove stale `staging/*.part` files and abandoned `work/` directories on startup
after checking that no live worker owns them. On failure, retain the raw source and
error metadata for inspection, but remove disposable work files. On success, retain
the source, manifest, scores, frames, and optional clips for the life of the video;
there is no automatic expiry in the local MVP. A future explicit video deletion
should remove the video directory and its database records as one coordinated
operation, making the API unavailable first and then deleting files. Do not delete
shared model files or other videos' data during cleanup.
