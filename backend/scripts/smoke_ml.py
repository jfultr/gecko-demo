"""Exercise real FFmpeg decoding and CLIP inference on one local video.

From backend: python scripts/smoke_ml.py /path/to/video.mp4
"""

import argparse
from hashlib import file_digest
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.db import Database
from app.media_probe import inspect_video
from app.ml.processor import process_video
from app.models.api import VideoManifest
from app.storage import video_dir
from app.worker import process_one


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    media_type, _, duration, width, height = inspect_video(source, source.name, None)
    with source.open("rb") as input_file:
        video_id = uuid5(NAMESPACE_URL, file_digest(input_file, "sha256").hexdigest())
    job_id = uuid5(video_id, "smoke")
    with TemporaryDirectory() as directory:
        outputs = []
        for attempt in (1, 2):
            settings = Settings(Path(directory) / f"run-{attempt}")
            settings.prepare()
            stored_source = video_dir(settings, video_id) / "source" / source.name
            stored_source.parent.mkdir(parents=True)
            shutil.copy2(source, stored_source)
            db = Database(settings.database_path)
            db.initialize()
            db.create_video_and_job(
                video_id=video_id, job_id=job_id, filename=source.name,
                source_relpath=stored_source.relative_to(settings.data_dir).as_posix(),
                media_type=media_type, duration_seconds=duration, width=width, height=height,
            )
            process_one(db, settings, process_video)
            job = db.get_job(job_id)
            if job["status"] != "completed":
                raise SystemExit(f"Worker failed: {job['error_code']}: {job['error_message']}")
            result = (settings.data_dir / job["result_relpath"]).parent
            manifest = VideoManifest.model_validate_json((result / "manifest.v1.json").read_bytes())
            required = [result / "scores.v1.json", result / "embeddings" / "vectors.npz",
                        result / "embeddings" / "metadata.json"]
            required.extend(result / "frames" / f"{peak.frame.frame_id}.jpg"
                            for peak in manifest.peaks)
            if not all(path.is_file() for path in required):
                raise SystemExit("Worker published incomplete result assets")
            outputs.append(manifest.model_dump_json())
        if outputs[0] != outputs[1]:
            raise SystemExit("Repeated inference produced different manifests")
        print(f"PASS: {media_type}, {len(manifest.samples)} samples, "
              f"{len(manifest.peaks)} peaks; repeated manifests match")


if __name__ == "__main__":
    main()
