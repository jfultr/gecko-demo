"""Exercise real FFmpeg decoding and CLIP inference on one local video.

From backend: python scripts/smoke_ml.py /path/to/video.mp4
"""

import argparse
from hashlib import file_digest
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.media_probe import inspect_video
from app.ml.processor import process_video
from app.processing import ProcessingContext


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
            work = Path(directory) / f"run-{attempt}"
            context = ProcessingContext(
                video_id=video_id, job_id=job_id, source=source, work_dir=work,
                filename=source.name, duration_seconds=duration, width=width,
                height=height, report_progress=lambda percent: None,
            )
            manifest = process_video(context)
            assert (work / "scores.v1.json").is_file()
            assert (work / "embeddings" / "vectors.npz").is_file()
            assert (work / "embeddings" / "metadata.json").is_file()
            assert all((work / "frames" / f"{peak.frame.frame_id}.jpg").is_file()
                       for peak in manifest.peaks)
            outputs.append(manifest.model_dump_json())
        if outputs[0] != outputs[1]:
            raise SystemExit("Repeated inference produced different manifests")
        print(f"PASS: {media_type}, {len(manifest.samples)} samples, "
              f"{len(manifest.peaks)} peaks; repeated manifests match")


if __name__ == "__main__":
    main()
