# Gecko Demo HTTP API v1

Status: contract for implementation (ROB-12). The Pydantic source of truth for JSON
shapes is [`backend/app/models/api.py`](../backend/app/models/api.py). All paths below
are relative to the same API origin. JSON responses use `application/json`; timestamps
are ISO 8601 with a timezone. Identifiers in path segments are opaque to clients.

The upload and job resources carry UUIDs. The manifest is independently versioned:
`schema_version: "1.0"` describes its data shape, while `/api/v1` versions the HTTP
interface. Clients should reject an unsupported `schema_version` rather than silently
rendering it.

## Upload and processing

### `POST /api/v1/videos`

Request: `multipart/form-data` with one `file` part containing the source video. The
part's filename is used as `video.filename`; its media type and actual content must
be validated by the server. No preset selection is accepted in v1: the processing
pipeline uses its configured preset, which is recorded in the manifest.

Success: `202 Accepted`, body `VideoUploadResponse`. This means the upload is stored
and queued, not that analysis has finished. The server must create the video and job
IDs before responding. A client may begin polling the returned job immediately.

```json
{
  "video_id": "6ba9acbb-a59b-4ba2-b383-d61a9fc3551a",
  "job_id": "09a5c8af-a53b-496e-96ae-44861904e2a9",
  "status": "queued"
}
```

The browser's upload progress measures bytes sent from the client to this endpoint.
After the `202` response, that indicator is complete; it must not be presented as the
job's analysis progress. Upload failure before a response can have an uncertain
outcome; v1 does not promise idempotent retries. Poll the returned job if its ID is
known, and otherwise ask the user before uploading the file again.

### `GET /api/v1/jobs/{job_id}`

Success: `200 OK`, body `JobResponse`, including for failed jobs. Poll while status is
`queued` or `processing`. Suggested client interval is 1–2 seconds, increasing on
transient network failures; an optional `Retry-After` response header takes priority.
Stop polling on `completed` or `failed`.

```json
{
  "job_id": "09a5c8af-a53b-496e-96ae-44861904e2a9",
  "video_id": "6ba9acbb-a59b-4ba2-b383-d61a9fc3551a",
  "status": "processing",
  "created_at": "2026-09-29T09:00:00Z",
  "updated_at": "2026-09-29T09:00:12Z",
  "progress_percent": 35,
  "error": null,
  "manifest_url": null
}
```

`progress_percent` is server-reported analysis progress on a 0–100 scale. `null` or
absence means it is unknown; the UI should use an indeterminate indicator. It is not
the upload percentage. When `completed`, `manifest_url` must be a fetchable path to
the manifest and `error` is `null`. When `failed`, `error` contains `ErrorDetail` and
`manifest_url` is `null`. A completed job must never expose a partially written
manifest. Job status moves `queued → processing → completed` or to `failed` from
either nonterminal state. A storage integrity check may exceptionally invalidate a
previously completed job and mark it `failed`; clients should treat the latest job
response as authoritative.

Completed example:

```json
{
  "job_id": "09a5c8af-a53b-496e-96ae-44861904e2a9",
  "video_id": "6ba9acbb-a59b-4ba2-b383-d61a9fc3551a",
  "status": "completed",
  "created_at": "2026-09-29T09:00:00Z",
  "updated_at": "2026-09-29T09:00:28Z",
  "progress_percent": 100,
  "error": null,
  "manifest_url": "/api/v1/videos/6ba9acbb-a59b-4ba2-b383-d61a9fc3551a/manifest"
}
```

Failed example (still HTTP `200`):

```json
{
  "job_id": "09a5c8af-a53b-496e-96ae-44861904e2a9",
  "video_id": "6ba9acbb-a59b-4ba2-b383-d61a9fc3551a",
  "status": "failed",
  "created_at": "2026-09-29T09:00:00Z",
  "updated_at": "2026-09-29T09:00:28Z",
  "progress_percent": null,
  "error": {
    "code": "PROCESSING_FAILED",
    "message": "The video could not be processed.",
    "retryable": false
  },
  "manifest_url": null
}
```

## Result and media

### `GET /api/v1/videos/{video_id}/manifest`

Success: `200 OK`, body `VideoManifest`. Available only after the corresponding job
is `completed`. Before then, return `409 Conflict` with `JOB_NOT_COMPLETE`; if the
job failed, return `409 Conflict` with `JOB_FAILED` and let the client fetch the job
for its detailed error. `404 Not Found` means the video ID does not exist. The
returned manifest's `video.video_id` must
match the path ID, and every media URL it contains must resolve for the lifetime of
the manifest. The manifest owns the exact preset, sampled scores, peak events, and
evidence frame references. The versioned fixture for this shape is tracked in ROB-11.

Each `samples[].score` and `peaks[].score` is a semantic similarity value from 0 to
100, not a calibrated probability or a safety verdict. `peaks[].level` is a display
category (`low`, `medium`, `high`). Timestamp fields are seconds from the beginning
of the source video. Consumers should use the server's timestamps rather than infer
them from sample array positions.

### `GET /api/v1/videos/{video_id}/source`

Success: `200 OK` for the full source video, or `206 Partial Content` for a valid
`Range: bytes=...` request. Use the stored media type as `Content-Type`, advertise
`Accept-Ranges: bytes`, and include `Content-Range` for partial responses. `416 Range
Not Satisfiable` includes `Content-Range: bytes */{size}`. This route is the value of
`video.source_url` in the manifest and supports native browser seeking. The response
body is video bytes, not a Pydantic JSON model.

### `GET /api/v1/videos/{video_id}/frames/{frame_id}`

Success: `200 OK` with the extracted image bytes and their image `Content-Type`.
This route is the value of `peaks[].frame.image_url`. `404 Not Found` applies if
either the video or frame is unknown. The response body is image bytes, not JSON.

The source video is available once upload returns `202`. A frame that is not yet
produced returns `409 Conflict` with `JOB_NOT_COMPLETE` (or `JOB_FAILED` if processing
failed). Clients should wait for a completed job before requesting media URLs from
its manifest. Media URL paths may be treated as opaque when consumed;
the explicit routes above describe the local v1 implementation.

## Errors

Non-success JSON responses use `ErrorResponse`, never a bare string. `code` is stable
for client branching; `message` is for display or logs; `retryable` tells the client
whether repeating the *same request* may help. It does not authorize blindly
repeating a possibly accepted upload.

| HTTP status | Code | When |
| --- | --- | --- |
| `400 Bad Request` | `INVALID_REQUEST` | Malformed multipart or request syntax |
| `404 Not Found` | `NOT_FOUND` | Unknown video, job, or frame ID |
| `409 Conflict` | `JOB_NOT_COMPLETE` | Result or media requested before processing completes |
| `409 Conflict` | `JOB_FAILED` | Result or media requested after processing failed |
| `413 Content Too Large` | `FILE_TOO_LARGE` | Upload exceeds configured limit |
| `415 Unsupported Media Type` | `UNSUPPORTED_VIDEO_FORMAT` | Unsupported upload format/content |
| `422 Unprocessable Content` | `INVALID_VIDEO` | Accepted format, but unreadable or invalid video |
| `500 Internal Server Error` | `INTERNAL_ERROR` | Unexpected server failure |
| `503 Service Unavailable` | `SERVICE_UNAVAILABLE` | Temporary inability to accept/process requests |

The service should map implementation errors to these codes consistently and avoid
exposing stack traces or local paths. A processing failure recorded in `JobResponse`
uses the same `ErrorDetail` shape, with `PROCESSING_FAILED` unless a more specific
stable code is defined. `retryable` is typically `false` for invalid content and
`true` for transient server failures.

Example `409` response:

```json
{
  "error": {
    "code": "JOB_NOT_COMPLETE",
    "message": "The video is still processing.",
    "retryable": true
  }
}
```

## Client sequence

1. Send the file to `POST /api/v1/videos`, showing transport upload progress.
2. Store `video_id` and `job_id` from the `202` response.
3. Poll `GET /api/v1/jobs/{job_id}`, showing analysis progress separately.
4. On `completed`, fetch `manifest_url`; render scores, peaks, and the returned
   `source_url` and `image_url` references.
5. On `failed`, show the job's `error.message` and stop polling.

The server implementation may expose OpenAPI from these Pydantic models. HTTP route
behavior in this document remains the contract for media bytes and state transitions,
which the JSON models alone do not express.
