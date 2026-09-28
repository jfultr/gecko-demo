"""Validate the v1 fixture against the backend contract and timeline invariants.

Run from the repository root: python fixtures/validate_manifest.py
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.models.api import VideoManifest  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    fixture = Path(__file__).with_name("manifest.v1.json")
    manifest = VideoManifest.model_validate_json(fixture.read_text(encoding="utf-8"))

    samples = manifest.samples
    timestamps = [sample.timestamp_seconds for sample in samples]
    require(bool(timestamps), "manifest needs at least one sample")
    require(timestamps == sorted(set(timestamps)), "samples must have unique ascending times")
    require(timestamps[-1] <= manifest.video.duration_seconds, "sample exceeds video duration")

    scores = {sample.timestamp_seconds: sample.score for sample in samples}
    require(len(manifest.peaks) >= 2, "fixture needs at least two peaks")
    video_url = f"/api/v1/videos/{manifest.video.video_id}"
    require(manifest.video.source_url == f"{video_url}/source", "source URL and video ID differ")
    require(
        len({peak.event_id for peak in manifest.peaks}) == len(manifest.peaks),
        "peak event IDs must be unique",
    )
    require(
        len({peak.frame.frame_id for peak in manifest.peaks}) == len(manifest.peaks),
        "evidence frame IDs must be unique",
    )
    for peak in manifest.peaks:
        require(peak.timestamp_seconds <= manifest.video.duration_seconds, "peak exceeds video duration")
        require(peak.frame.timestamp_seconds == peak.timestamp_seconds, "frame and peak times differ")
        require(scores.get(peak.timestamp_seconds) == peak.score, "peak does not match sample")
        require(peak.prompt in manifest.preset.positive_prompts, "peak prompt is absent from preset")
        require(
            peak.frame.image_url == f"{video_url}/frames/{peak.frame.frame_id}",
            "frame URL, video ID and frame ID differ",
        )

    print(f"Valid {manifest.schema_version} manifest: {len(samples)} samples, {len(manifest.peaks)} peaks")


if __name__ == "__main__":
    main()
