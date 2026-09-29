import json
from pathlib import Path
import tempfile
import unittest

from app.ml.config import ModelConfig, load_preset
from app.processing import ProcessingError


class ModelConfigTests(unittest.TestCase):
    def test_default_model_and_preset(self):
        self.assertEqual(ModelConfig().model_id, "openai/clip-vit-base-patch32")
        preset = load_preset()
        self.assertEqual(preset.preset_id, "warehouse-hazards-v1")
        self.assertTrue(preset.positive_prompts)
        self.assertTrue(preset.negative_prompts)

    def test_external_preset_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presets.json"
            path.write_text(json.dumps({"presets": [{
                "preset_id": "custom-v2", "label": "Custom",
                "positive_prompts": ["A person near a moving robot"],
                "negative_prompts": ["An empty room"],
            }]}), encoding="utf-8")
            self.assertEqual(load_preset(path, "custom-v2").positive_prompts[0],
                             "A person near a moving robot")

    def test_missing_or_blank_preset_is_error(self):
        with self.assertRaises(ProcessingError):
            load_preset(preset_id="missing")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presets.json"
            path.write_text('{"presets":[{"preset_id":"bad","label":"Bad",'
                            '"positive_prompts":[" "]}]}', encoding="utf-8")
            with self.assertRaises(ProcessingError):
                load_preset(path, "bad")
