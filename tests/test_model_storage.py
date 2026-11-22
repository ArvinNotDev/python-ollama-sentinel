import tempfile
import unittest
from pathlib import Path

from core.ollama.model_storage import move_model_directory


class ModelStorageTests(unittest.TestCase):
    def test_moves_existing_model_tree_to_new_location(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "old-models"
            destination = root / "new-drive" / "ollama-models"
            (source / "blobs").mkdir(parents=True)
            (source / "manifests" / "registry.ollama.ai" / "library" / "qwen3").mkdir(parents=True)
            (source / "blobs" / "sha256-test").write_bytes(b"model-data")
            (source / "manifests" / "registry.ollama.ai" / "library" / "qwen3" / "8b").write_text(
                "manifest", encoding="utf-8"
            )

            result = move_model_directory(source, destination)

            self.assertEqual(result, destination.resolve())
            self.assertFalse(source.exists())
            self.assertEqual((destination / "blobs" / "sha256-test").read_bytes(), b"model-data")

    def test_refuses_non_empty_destination_without_touching_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            (source / "model").write_text("source", encoding="utf-8")
            (destination / "keep").write_text("existing", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                move_model_directory(source, destination)

            self.assertTrue((source / "model").is_file())
            self.assertEqual((destination / "keep").read_text(encoding="utf-8"), "existing")

    def test_refuses_nested_paths_and_same_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "models"
            source.mkdir()
            with self.assertRaises(ValueError):
                move_model_directory(source, source)
            with self.assertRaises(ValueError):
                move_model_directory(source, source / "nested")
            with self.assertRaises(ValueError):
                move_model_directory(source, root)

    def test_refuses_missing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                move_model_directory(Path(directory) / "missing", Path(directory) / "target")


if __name__ == "__main__":
    unittest.main()
