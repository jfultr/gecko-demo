from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import numpy as np

from app.ml.sampling import midpoint_targets, sampled_timestamps
from app.ml.scoring import ScoredFrame, peak_indices, risk_level, score_frame, smooth_scores
from app.processing import ProcessingError


class SamplingTests(unittest.TestCase):
    def test_midpoints_follow_architecture(self):
        self.assertEqual(midpoint_targets(2), [0.5, 1.5])
        self.assertEqual(len(midpoint_targets(1000)), 180)
        with self.assertRaises(ProcessingError):
            midpoint_targets(0)

    @patch("app.ml.sampling.subprocess.run")
    def test_nearest_real_timestamps_are_unique(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "0.0\n0.4\n1.4\n", "")
        self.assertEqual(sampled_timestamps(Path("video.mp4"), 3), [0.4, 1.4])

    @patch("app.ml.sampling.subprocess.run")
    def test_missing_frames_fail(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        with self.assertRaises(ProcessingError):
            sampled_timestamps(Path("video.mp4"), 1)


class ScoringTests(unittest.TestCase):
    def test_fixed_mapping_and_winning_prompt(self):
        image = np.array([1.0, 0.0], dtype=np.float32)
        text = np.array([[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]], dtype=np.float32)
        score, prompt = score_frame(image, text, ["hazard one", "hazard two"])
        self.assertGreater(score, 99)
        self.assertEqual(prompt, "hazard one")
        self.assertAlmostEqual(score_frame(image, text, ["hazard one", "hazard two"])[0], score)

    def test_smoothing_peaks_and_levels(self):
        raw = [10, 80, 90, 85, 10, 10, 90, 90, 10]
        frames = [ScoredFrame(float(i * 2), float(value), "prompt", f"frame-{i:06d}")
                  for i, value in enumerate(raw)]
        smoothed = smooth_scores(frames)
        self.assertEqual(smoothed[2], 85)
        self.assertEqual(peak_indices(frames, smoothed), [6, 2])
        self.assertEqual([risk_level(value) for value in [39.9, 40, 75]],
                         ["low", "medium", "high"])

    def test_non_finite_similarity_is_rejected(self):
        with self.assertRaises(ProcessingError):
            score_frame(np.array([float("nan")]), np.array([[1.0]]), ["hazard"])
