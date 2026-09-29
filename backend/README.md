# Gecko Demo backend

The API and worker share an absolute `APP_DATA_DIR` outside this repository. The
directory contains SQLite metadata, uploaded sources, and published results.

Install the Python packages from `requirements.txt` and make `ffprobe` (from
FFmpeg) available on `PATH`. From this directory, start the API with:

```sh
export APP_DATA_DIR=/absolute/path/to/gecko-data
uvicorn app.main:app
```

Run the worker as a separate process with the same `APP_DATA_DIR`. Install
FFmpeg (`ffmpeg` and `ffprobe`) on `PATH`. The first run downloads the default
`openai/clip-vit-base-patch32` model at a pinned revision unless it is already
cached:

```sh
python -m app.worker
```

The processor receives a
`ProcessingContext`, writes derived files beneath `work_dir`, and returns a
`VideoManifest`. The worker validates and publishes the result before changing
the job status to `completed`. The default processor performs CPU inference with
PyTorch and Hugging Face Transformers. Set `APP_ML_DEVICE` to a supported Torch
device such as `cuda` when available. Set `APP_ML_MODEL_ID` and
`APP_ML_MODEL_REVISION` to select a compatible CLIP checkpoint; keep the revision
at an immutable commit for repeatable deployments. `APP_ML_PRESETS_FILE` can
point to a JSON file with a `presets` array, and `APP_ML_PRESET_ID` selects one
entry. `APP_PROCESSOR` may override the callable for development.

The score is a fixed sigmoid mapping of the difference between maximum positive
and negative cosine similarities, followed by a three-sample median filter. It is
a semantic similarity indicator, not a calibrated probability or safety verdict.
The `embeddings/metadata.json` file records the model revision and preprocessing,
scoring, smoothing and preset identifiers used for each result. For local use,
check the chosen model's license and available RAM/GPU memory before running.

To verify real decoding and inference on a local video, run
`python scripts/smoke_ml.py /absolute/path/to/video.mp4` from `backend/`. It
processes the video twice and checks that the manifests match.

`APP_MAX_UPLOAD_BYTES` optionally changes the upload limit (default: 2 GiB).
The HTTP routes and response shapes are specified in `docs/api-v1.md`.
