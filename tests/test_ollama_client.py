import json
import unittest
from unittest.mock import MagicMock

from core.ollama.ollama_commands import OllamaClient, OllamaError
from core.ollama.process_manager import OllamaProcessManager


class FakeResponse:
    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=False):
        return iter(self.lines)


class OllamaClientTests(unittest.TestCase):
    def test_pull_stream_yields_progress_events(self):
        client = OllamaClient()
        client.session.post = MagicMock(return_value=FakeResponse([
            json.dumps({"status": "pulling manifest"}),
            json.dumps({"status": "downloading", "completed": 50, "total": 100}),
            json.dumps({"status": "success"}),
        ]))
        events = list(client.pull_model("qwen3:4b"))
        self.assertEqual(events[1]["completed"], 50)
        self.assertEqual(events[-1]["status"], "success")
        client.close()

    def test_api_error_is_raised(self):
        with self.assertRaises(OllamaError):
            OllamaClient._raise_for_api_error({"error": "model not found"})

    def test_invalid_endpoint_is_rejected(self):
        with self.assertRaises(ValueError):
            OllamaClient("not-a-url")

    def test_managed_server_refuses_remote_bind_address(self):
        manager = OllamaProcessManager()
        started, message = manager.start("/tmp/sentinel-models", "https://example.com:11434")
        self.assertFalse(started)
        self.assertIn("local HTTP address", message)


if __name__ == "__main__":
    unittest.main()
