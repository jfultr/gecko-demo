import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import numpy as np

from app.config import Settings
from app.db import Database
from app.ml.processor import process_video
from app.processing import ProcessingContext, ProcessingError
from app.storage import video_dir
from app.worker import process_one


class FakeEncoder:
    preprocessing_revision = "fake-v1"
    resolved_revision = "fake-commit"

    def __init__(self, config):
        self.config = config

    def encode_text(self, prompts):
        # All positive prompts describe the same positive direction.
        return np.array([[1.0, 0.0]] * 3 + [[-1.0, 0.0]] * 3, dtype=np.float32)

    def encode_image(self, image_path):
        index = int(image_path.stem.split("-")[-1])
        return np.array([1.0 if index in (1, 2, 3) else -1.0, 0.0], dtype=np.float32)


def fake_extract(source, timestamp, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"jpeg evidence")


class ProcessorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.mp4"
        self.source.write_bytes(b"fixed video bytes")
        os.utime(self.source, (1_700_000_000, 1_700_000_000))
        self.video_id = uuid4()
        self.job_id = uuid4()
        self.patches = [
            patch("app.ml.processor.sampled_timestamps", return_value=[1., 2., 3., 8., 9.]),
            patch("app.ml.processor.extract_frame", side_effect=fake_extract),
            patch("app.ml.processor.ClipEncoder", FakeEncoder),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def context(self, work_dir):
        return ProcessingContext(
            video_id=self.video_id, job_id=self.job_id, source=self.source,
            work_dir=work_dir, filename="source.mp4", duration_seconds=10,
            width=640, height=480, report_progress=lambda value: None,
        )

    def test_manifest_vectors_scores_and_evidence_are_deterministic(self):
        first = process_video(self.context(self.root / "first"))
        second = process_video(self.context(self.root / "second"))
        self.assertEqual(first.model_dump_json(), second.model_dump_json())
        self.assertEqual(len(first.samples), 5)
        self.assertEqual(len(first.peaks), 1)
        self.assertEqual(first.peaks[0].frame.frame_id, "frame-000001")
        self.assertEqual(first.score_label, "semantic_similarity")
        self.assertFalse((self.root / "first" / "sampled").exists())
        self.assertTrue((self.root / "first" / "frames" / "frame-000001.jpg").exists())
        with np.load(self.root / "first" / "embeddings" / "vectors.npz") as stored:
            self.assertEqual(stored["vectors"].shape, (5, 2))
            self.assertEqual(stored["timestamps"].tolist(), [1., 2., 3., 8., 9.])
        metadata = json.loads((self.root / "first" / "embeddings" / "metadata.json").read_text())
        self.assertEqual(metadata["model_revision"], "fake-commit")
        self.assertEqual(metadata["preset_id"], "warehouse-hazards-v1")

    def test_worker_publishes_result_and_structured_failure(self):
        settings = Settings(self.root / "data")
        settings.prepare()
        db = Database(settings.database_path)
        db.initialize()
        source = video_dir(settings, self.video_id) / "source" / "original.mp4"
        source.parent.mkdir(parents=True)
        source.write_bytes(self.source.read_bytes())
        db.create_video_and_job(
            video_id=self.video_id, job_id=self.job_id, filename="source.mp4",
            source_relpath=source.relative_to(settings.data_dir).as_posix(),
            media_type="video/mp4", duration_seconds=10, width=640, height=480,
        )
        self.assertTrue(process_one(db, settings, process_video))
        job = db.get_job(self.job_id)
        self.assertEqual(job["status"], "completed")
        self.assertTrue((settings.data_dir / job["result_relpath"]).is_file())

        second_id = uuid4()
        second_source = video_dir(settings, second_id) / "source" / "original.mp4"
        second_source.parent.mkdir(parents=True)
        second_source.write_bytes(self.source.read_bytes())
        db.create_video_and_job(
            video_id=second_id, job_id=uuid4(), filename="source.mp4",
            source_relpath=second_source.relative_to(settings.data_dir).as_posix(),
            media_type="video/mp4", duration_seconds=10, width=640, height=480,
        )
        with patch("app.ml.processor.sampled_timestamps", side_effect=ProcessingError(
            "VIDEO_DECODE_FAILED", "Could not decode.")):
            self.assertTrue(process_one(db, settings, process_video))
        self.assertEqual(db.get_video_job(second_id)["error_code"], "VIDEO_DECODE_FAILED")
