# Gecko Demo backend

The API and worker share an absolute `APP_DATA_DIR` outside this repository. The
directory contains SQLite metadata, uploaded sources, and published results.

Install the Python packages from `requirements.txt` and make `ffprobe` (from
FFmpeg) available on `PATH`. From this directory, start the API with:

```sh
export APP_DATA_DIR=/absolute/path/to/gecko-data
uvicorn app.main:app
```

Run the worker as a separate process with the same `APP_DATA_DIR`:

```sh
export APP_PROCESSOR=package.module:function
python -m app.worker
```

The processor callable is supplied by ROB-3. It receives a
`ProcessingContext`, writes derived files beneath `work_dir`, and returns a
`VideoManifest`. The worker validates and publishes the result before changing
the job status to `completed`. Until a processor is configured, accepted jobs
remain `queued`.

`APP_MAX_UPLOAD_BYTES` optionally changes the upload limit (default: 2 GiB).
The HTTP routes and response shapes are specified in `docs/api-v1.md`.
