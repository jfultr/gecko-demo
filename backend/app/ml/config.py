"""Worker-only model and prompt configuration."""

from dataclasses import dataclass
import json
import os
from pathlib import Path

from pydantic import ValidationError

from ..models.api import PromptPreset
from ..processing import ProcessingError


DEFAULT_PRESETS = Path(__file__).with_name("presets.json")


@dataclass(frozen=True)
class ModelConfig:
    model_id: str = "openai/clip-vit-base-patch32"
    revision: str = "main"
    device: str = "cpu"

    @classmethod
    def from_env(cls) -> "ModelConfig":
        return cls(
            model_id=os.environ.get("APP_ML_MODEL_ID", cls.model_id),
            revision=os.environ.get("APP_ML_MODEL_REVISION", cls.revision),
            device=os.environ.get("APP_ML_DEVICE", cls.device),
        )


def load_preset(path: Path | None = None, preset_id: str | None = None) -> PromptPreset:
    """Load a preset from a versioned data file, never from UI code."""
    selected_path = path or Path(os.environ.get("APP_ML_PRESETS_FILE", DEFAULT_PRESETS))
    selected_id = preset_id or os.environ.get("APP_ML_PRESET_ID", "warehouse-hazards-v1")
    try:
        data = json.loads(selected_path.read_text(encoding="utf-8"))
        presets = [PromptPreset.model_validate(item) for item in data["presets"]]
    except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
        raise ProcessingError("PRESET_INVALID", "The semantic prompt preset file is invalid.") from exc
    matches = [preset for preset in presets if preset.preset_id == selected_id]
    if len(matches) != 1 or not all(
        prompt.strip() for preset in presets
        for prompt in preset.positive_prompts + preset.negative_prompts
    ):
        raise ProcessingError("PRESET_INVALID", "The semantic prompt preset is missing or invalid.")
    return matches[0]
