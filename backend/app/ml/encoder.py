"""PyTorch-backed CLIP embeddings, isolated from scoring and video I/O."""

from pathlib import Path

import numpy as np

from ..processing import ProcessingError
from .config import ModelConfig


class ClipEncoder:
    preprocessing_revision = "clip-processor-v1"

    def __init__(self, config: ModelConfig):
        self.config = config
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            self._torch = torch
            self._processor = CLIPProcessor.from_pretrained(
                config.model_id, revision=config.revision
            )
            self._model = CLIPModel.from_pretrained(
                config.model_id, revision=config.revision
            ).to(config.device).eval()
            self.resolved_revision = getattr(self._model.config, "_commit_hash", None) or config.revision
        except Exception as exc:
            raise ProcessingError("MODEL_UNAVAILABLE", "The configured CLIP model could not be loaded.") from exc

    def _normalized(self, features) -> np.ndarray:
        vector = features.detach().cpu().numpy().astype(np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm <= 0:
            raise ProcessingError("INFERENCE_FAILED", "The model returned an invalid embedding.")
        return vector / norm

    def encode_text(self, prompts: list[str]) -> np.ndarray:
        if not prompts:
            raise ProcessingError("PRESET_INVALID", "At least one prompt is required.")
        try:
            inputs = self._processor(text=prompts, return_tensors="pt", padding=True)
            inputs = {key: value.to(self.config.device) for key, value in inputs.items()}
            with self._torch.inference_mode():
                features = self._model.get_text_features(**inputs)
            return np.stack([self._normalized(item) for item in features])
        except ProcessingError:
            raise
        except Exception as exc:
            raise ProcessingError("INFERENCE_FAILED", "Text embedding failed.") from exc

    def encode_image(self, image_path: Path) -> np.ndarray:
        try:
            from PIL import Image

            with Image.open(image_path) as image:
                inputs = self._processor(images=image.convert("RGB"), return_tensors="pt")
            inputs = {key: value.to(self.config.device) for key, value in inputs.items()}
            with self._torch.inference_mode():
                features = self._model.get_image_features(**inputs)
            return self._normalized(features[0])
        except ProcessingError:
            raise
        except Exception as exc:
            raise ProcessingError("INFERENCE_FAILED", "Image embedding failed.") from exc
