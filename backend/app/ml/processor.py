"""ROB-3 processor invoked by the durable backend worker."""

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np

from ..models.api import EvidenceFrame, PeakEvent, RiskSample, VideoInfo, VideoManifest
from ..processing import ProcessingContext, ProcessingError
from .config import ModelConfig, load_preset
from .encoder import ClipEncoder
from .sampling import extract_frame, sampled_timestamps
from .scoring import SCORING_VERSION, SMOOTHING_VERSION, ScoredFrame, peak_indices, risk_level, score_frame, smooth_scores


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def process_video(context: ProcessingContext) -> VideoManifest:
    """Produce retained vectors, score data, evidence frames and a v1 manifest."""
    if not context.duration_seconds or not context.width or not context.height:
        raise ProcessingError("INVALID_VIDEO", "The source video has incomplete metadata.")
    duration = context.duration_seconds
    timestamps = sampled_timestamps(context.source, duration)
    preset = load_preset()
    encoder = ClipEncoder(ModelConfig.from_env())
    prompts = preset.positive_prompts + preset.negative_prompts
    text_vectors = encoder.encode_text(prompts)
    context.report_progress(5)

    sampled_dir = context.work_dir / "sampled"
    vectors: list[np.ndarray] = []
    frames: list[ScoredFrame] = []
    try:
        for index, timestamp in enumerate(timestamps):
            frame_id = f"frame-{index:06d}"
            image = sampled_dir / f"{frame_id}.jpg"
            extract_frame(context.source, timestamp, image)
            vector = encoder.encode_image(image)
            raw_score, prompt = score_frame(vector, text_vectors, preset.positive_prompts)
            vectors.append(vector)
            frames.append(ScoredFrame(timestamp, round(raw_score, 4), prompt, frame_id))
            context.report_progress(5 + int(85 * (index + 1) / len(timestamps)))

        smoothed = [round(value, 4) for value in smooth_scores(frames)]
        peaks = []
        evidence_dir = context.work_dir / "frames"
        for index in peak_indices(frames, smoothed):
            item = frames[index]
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (sampled_dir / f"{item.frame_id}.jpg").replace(evidence_dir / f"{item.frame_id}.jpg")
            peaks.append(PeakEvent(
                event_id=f"peak-{index:06d}",
                timestamp_seconds=item.timestamp,
                score=smoothed[index],
                level=risk_level(smoothed[index]),
                frame=EvidenceFrame(
                    frame_id=item.frame_id,
                    timestamp_seconds=item.timestamp,
                    image_url=f"/api/v1/videos/{context.video_id}/frames/{item.frame_id}",
                ),
                prompt=item.prompt,
            ))

        embeddings = context.work_dir / "embeddings"
        embeddings.mkdir(parents=True, exist_ok=True)
        matrix = np.stack(vectors).astype(np.float32)
        np.savez_compressed(
            embeddings / "vectors.npz",
            timestamps=np.asarray(timestamps, dtype=np.float64),
            vectors=matrix,
        )
        _write_json(embeddings / "metadata.json", {
            "encoder_id": encoder.config.model_id,
            "model_revision": encoder.resolved_revision,
            "preprocessing_revision": encoder.preprocessing_revision,
            "vector_dimension": int(matrix.shape[1]),
            "dtype": "float32",
            "normalization": "unit_l2",
            "scoring_version": SCORING_VERSION,
            "smoothing_version": SMOOTHING_VERSION,
            "preset_id": preset.preset_id,
            "positive_prompts": preset.positive_prompts,
            "negative_prompts": preset.negative_prompts,
        })
        _write_json(context.work_dir / "scores.v1.json", {
            "schema_version": "1.0",
            "score_label": "semantic_similarity",
            "scoring_version": SCORING_VERSION,
            "smoothing_version": SMOOTHING_VERSION,
            "samples": [
                {"frame_id": item.frame_id, "timestamp_seconds": item.timestamp,
                 "raw_score": item.raw_score, "score": smoothed[index], "prompt": item.prompt}
                for index, item in enumerate(frames)
            ],
        })
        manifest = VideoManifest(
            video=VideoInfo(
                video_id=context.video_id, filename=context.filename,
                source_url=f"/api/v1/videos/{context.video_id}/source",
                duration_seconds=duration, width=context.width, height=context.height,
            ),
            # Source mtime is stable across a retry of the same uploaded video.
            generated_at=datetime.fromtimestamp(context.source.stat().st_mtime, timezone.utc),
            preset=preset,
            samples=[RiskSample(timestamp_seconds=item.timestamp, score=smoothed[index])
                     for index, item in enumerate(frames)],
            peaks=peaks,
        )
        context.report_progress(95)
        return manifest
    finally:
        shutil.rmtree(sampled_dir, ignore_errors=True)
