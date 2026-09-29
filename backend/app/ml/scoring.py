"""Fixed zero-shot score mapping and temporal peak selection."""

from dataclasses import dataclass
import math
from statistics import median

import numpy as np

from ..processing import ProcessingError


SCORING_VERSION = "cosine-margin-sigmoid-v1"
SMOOTHING_VERSION = "median-3-v1"


@dataclass(frozen=True)
class ScoredFrame:
    timestamp: float
    raw_score: float
    prompt: str
    frame_id: str


def score_frame(image: np.ndarray, text: np.ndarray, positive_prompts: list[str]) -> tuple[float, str]:
    """Map max-positive minus max-negative cosine similarity to a fixed 0–100 scale."""
    count = len(positive_prompts)
    if count < 1 or text.ndim != 2 or image.ndim != 1 or text.shape[0] < count or text.shape[1] != image.shape[0]:
        raise ProcessingError("INFERENCE_FAILED", "Embedding dimensions or prompt counts do not match.")
    similarities = text @ image
    if not np.all(np.isfinite(similarities)):
        raise ProcessingError("INFERENCE_FAILED", "The model returned an invalid similarity.")
    positive = similarities[:count]
    winning_index = int(np.argmax(positive))
    negative_max = float(np.max(similarities[count:])) if text.shape[0] > count else 0.0
    margin = float(positive[winning_index]) - negative_max
    score = 100.0 / (1.0 + math.exp(-10.0 * margin))
    return score, positive_prompts[winning_index]


def smooth_scores(frames: list[ScoredFrame]) -> list[float]:
    return [float(median(frame.raw_score for frame in frames[max(0, i - 1):i + 2]))
            for i in range(len(frames))]


def peak_indices(frames: list[ScoredFrame], scores: list[float]) -> list[int]:
    if len(frames) != len(scores):
        raise ValueError("Frames and scores must align")
    if len(scores) > 1 and max(scores) == min(scores):
        return []
    candidates = []
    for index, score in enumerate(scores):
        left = scores[index - 1] if index else float("-inf")
        right = scores[index + 1] if index + 1 < len(scores) else float("-inf")
        # Resolve plateaus to the first sample.
        if score >= 60 and score >= left and score >= right and (score > left or score > right):
            if index and score == left:
                continue
            candidates.append(index)
    selected = []
    for index in sorted(candidates, key=lambda item: (-scores[item], frames[item].timestamp)):
        if all(abs(frames[index].timestamp - frames[other].timestamp) >= 5 for other in selected):
            selected.append(index)
        if len(selected) == 5:
            break
    return selected


def risk_level(score: float) -> str:
    return "low" if score < 40 else "medium" if score < 75 else "high"
