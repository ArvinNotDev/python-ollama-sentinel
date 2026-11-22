import base64
import tempfile
import unittest
from pathlib import Path

from core.attachments import AttachmentError, prepare_attachment


class AttachmentTests(unittest.TestCase):
    def test_text_file_is_extracted(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "notes.md"
            path.write_text("# Notes\nA useful document.", encoding="utf-8")
            result = prepare_attachment(path)
            self.assertEqual(result["kind"], "file")
            self.assertIn("A useful document.", result["text"])
            self.assertEqual(result["name"], "notes.md")

    def test_csv_is_extracted_as_readable_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "table.csv"
            path.write_text("Name,Score\nArvin,20\n", encoding="utf-8")
            result = prepare_attachment(path)
            self.assertIn("Name | Score", result["text"])
            self.assertIn("Arvin | 20", result["text"])

    def test_image_is_base64_encoded(self):
        payload = b"not-a-real-png-but-raw-bytes"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "photo.png"
            path.write_bytes(payload)
            result = prepare_attachment(path)
            self.assertEqual(result["kind"], "image")
            self.assertEqual(result["mime_type"], "image/png")
            self.assertEqual(base64.b64decode(result["data"]), payload)

    def test_unsupported_extension_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "archive.zip"
            path.write_bytes(b"zip")
            with self.assertRaises(AttachmentError):
                prepare_attachment(path)


if __name__ == "__main__":
    unittest.main()
