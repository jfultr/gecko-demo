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
The frontend opens the upload screen. Drop or select an MP4, MOV, or WebM video,
then choose **Analyze video**. The screen shows upload transfer progress, followed
by the queued and processing job states. When the worker completes, the result
opens in the video review screen. **View demo analysis** opens the fixture without
uploading a video.

To exercise the backend directly, upload a local video:

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
limit can be changed with `APP_MAX_UPLOAD_BYTES`; Compose passes the same limit
to the frontend for early validation. The API remains authoritative for video
format and content validation. A failed processing job displays the worker's
error and lets the user start a new analysis.

If you also run `npm run dev` separately on port 5173, that session needs its
own API proxy target. Its default is `http://127.0.0.1:8000`; when Compose
publishes the Gecko API on another port, set `VITE_API_TARGET` in
`frontend/.env.local` to that origin and restart Vite. Open the Compose frontend
on the port specified by `FRONTEND_PORT`.

To repeat the API path through the frontend proxy with the bundled demo video:

```sh
python scripts/smoke_upload_flow.py --base-url http://localhost:5173
```

The smoke check verifies a structured invalid-format response, upload acceptance,
job completion, manifest retrieval, and video playback bytes. Allow extra time on
the first run while the worker downloads its model.

## Checks

CI runs backend unit tests, validates the shared manifest fixture, builds the
frontend, and starts the Compose stack to check API readiness and frontend API
proxying on pull requests and pushes to `master`.

For individual service setup and processor configuration, see
[`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md).
