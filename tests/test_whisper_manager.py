import tempfile
import unittest
from pathlib import Path

from core.speech.whisper_manager import WHISPER_MODELS, WhisperModelManager


class WhisperManagerTests(unittest.TestCase):
    def test_supported_models_are_multilingual_faster_whisper_repositories(self):
        self.assertIn("tiny", WHISPER_MODELS)
        self.assertIn("base", WHISPER_MODELS)
        self.assertIn("small", WHISPER_MODELS)
        self.assertIn("distil-large-v3", WHISPER_MODELS)
        self.assertIn("large-v3-turbo", WHISPER_MODELS)
        self.assertTrue(WHISPER_MODELS["base"]["repo_id"].startswith("Systran/faster-whisper-"))

    def test_installed_model_detection_checks_required_files(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = WhisperModelManager(directory)
            model_dir = Path(directory) / "base"
            model_dir.mkdir()
            self.assertFalse(manager.is_installed("base"))
            for filename in ("model.bin", "config.json", "tokenizer.json"):
                (model_dir / filename).write_bytes(b"test")
            self.assertTrue(manager.is_installed("base"))
            self.assertEqual(manager.installed_models(), ["base"])

    def test_model_paths_are_scoped_to_voice_model_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = WhisperModelManager(directory)
            self.assertEqual(manager.model_path("small"), Path(directory) / "small")

    def test_unknown_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = WhisperModelManager(directory)
            with self.assertRaises(ValueError):
                manager.model_path("not-a-whisper-model")


if __name__ == "__main__":
    unittest.main()
