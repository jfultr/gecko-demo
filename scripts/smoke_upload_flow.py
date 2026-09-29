"""Exercise the frontend proxy, upload API, worker, manifest, and video source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


FIXTURE = Path(__file__).resolve().parents[1] / "frontend/public/demo/warehouse-walkthrough.mp4"


def upload(base_url: str, filename: str, content_type: str, content: bytes) -> tuple[int, dict]:
    boundary = f"gecko-smoke-{uuid4().hex}"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    request = Request(
        f"{base_url}/api/v1/videos",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def read_json(url: str) -> dict:
    with urlopen(url, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected HTTP {response.status}: {url}")
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5173", help="Frontend origin with /api proxy")
    parser.add_argument("--timeout", type=int, default=600, help="Maximum worker wait in seconds")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    invalid_status, invalid_body = upload(base_url, "invalid.txt", "text/plain", b"not a video")
    if invalid_status != 415 or invalid_body.get("error", {}).get("code") != "UNSUPPORTED_VIDEO_FORMAT":
        raise RuntimeError(f"Unexpected invalid-file response: {invalid_status} {invalid_body}")
    print("Unsupported format: structured 415 response")

    status, accepted = upload(base_url, FIXTURE.name, "video/mp4", FIXTURE.read_bytes())
    if status != 202 or accepted.get("status") != "queued":
        raise RuntimeError(f"Upload was not accepted: {status} {accepted}")
    job_id, video_id = accepted["job_id"], accepted["video_id"]
    print(f"Upload accepted: job {job_id}")

    deadline = time.monotonic() + args.timeout
    last_status = None
    while time.monotonic() < deadline:
        job = read_json(f"{base_url}/api/v1/jobs/{job_id}")
        if job.get("job_id") != job_id or job.get("video_id") != video_id:
            raise RuntimeError("Job identifiers do not match the accepted upload")
        if job["status"] != last_status:
            print(f"Job status: {job['status']}")
            last_status = job["status"]
        if job["status"] == "failed":
            raise RuntimeError(f"Worker failed: {job.get('error')}")
        if job["status"] == "completed":
            break
        time.sleep(1.5)
    else:
        raise TimeoutError(f"Job did not complete within {args.timeout} seconds")

    manifest_url = job.get("manifest_url")
    if not isinstance(manifest_url, str) or not manifest_url.startswith("/api/v1/videos/"):
        raise RuntimeError(f"Invalid manifest URL: {manifest_url}")
    manifest = read_json(base_url + manifest_url)
    if manifest.get("schema_version") != "1.0" or manifest.get("video", {}).get("video_id") != video_id:
        raise RuntimeError("Manifest version or video ID does not match the upload")
    if not manifest.get("samples"):
        raise RuntimeError("Completed manifest has no score samples")

    source_url = manifest["video"]["source_url"]
    if not isinstance(source_url, str) or not source_url.startswith("/api/v1/videos/"):
        raise RuntimeError(f"Invalid source URL: {source_url}")
    request = Request(base_url + source_url, headers={"Range": "bytes=0-31"})
    with urlopen(request, timeout=30) as response:
        if response.status != 206 or not response.read():
            raise RuntimeError("Source video range request failed")
    print(f"Manifest and video source ready: {len(manifest['samples'])} score samples")


if __name__ == "__main__":
    main()
