# Gecko Demo

Gecko Demo is a local video analysis app with a React review screen, a FastAPI
upload and results API, and a background worker that scores video frames.

## Run the full local stack

Install Docker Desktop (or Docker Engine with the Compose plugin), then run from
the repository root:

```sh
docker compose up --build
```

Open the frontend at <http://localhost:5173/> and the API docs at
<http://localhost:8000/docs>. The API, worker, and frontend proxy run together.
The frontend currently opens its review fixture; `/api` requests are proxied to
the real API for the upload flow being added in ROB-4.

To exercise the backend before the upload UI lands, upload a local video:

```sh
curl -F 'file=@/absolute/path/to/video.mp4' http://localhost:8000/api/v1/videos
```

The response includes `job_id` and `video_id`. Poll
`http://localhost:8000/api/v1/jobs/<job_id>` until the status is `completed` or
`failed`, then fetch
`http://localhost:8000/api/v1/videos/<video_id>/manifest` when complete. The
first processing run downloads the CLIP model into the persistent cache volume.

The first Docker build installs the CPU PyTorch/Transformers runtime. The first
processed upload downloads the configured CLIP model and may take several
minutes. Model files and uploaded videos persist in the `model_cache` and
`gecko_data` Docker volumes. Use `docker compose down` to stop the stack while
keeping those files. `docker compose down -v` also deletes them.

Override the host ports with `FRONTEND_PORT` and `API_PORT`. The upload size
limit can be changed with `APP_MAX_UPLOAD_BYTES`.

## Checks

CI runs backend unit tests, validates the shared manifest fixture, builds the
frontend, and starts the Compose stack to check API readiness and frontend API
proxying on pull requests and pushes to `master`.

For individual service setup and processor configuration, see
[`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md).
