import json
import unittest
from unittest.mock import MagicMock

import requests

from core.providers import ProviderError, RemoteProviderClient


class FakeResponse:
    def __init__(self, payload=None, lines=None, status=200):
        self.payload = payload or {}
        self.lines = lines or []
        self.status_code = status
        self.ok = status < 400
        self.text = json.dumps(self.payload)

    def json(self):
        return self.payload

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(response=self)

    def iter_lines(self, decode_unicode=False):
        return iter(self.lines)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class RemoteProviderTests(unittest.TestCase):
    def test_openai_compatible_model_discovery(self):
        session = MagicMock()
        session.request.return_value = FakeResponse({"data": [{"id": "model-a"}, {"id": "model-b"}]})
        client = RemoteProviderClient(
            {"provider": "openai_compatible", "base_url": "https://example.test/v1"},
            "token", session=session,
        )
        models = client.list_models()
        self.assertEqual([item["id"] for item in models], ["model-a", "model-b"])
        self.assertEqual(session.request.call_args.args[1], "https://example.test/v1/models")
        self.assertEqual(session.request.call_args.kwargs["headers"]["Authorization"], "Bearer token")

    def test_anthropic_model_discovery_uses_api_headers(self):
        session = MagicMock()
        session.request.return_value = FakeResponse({"data": [{"id": "claude-sonnet-x"}]})
        client = RemoteProviderClient(
            {"provider": "anthropic", "base_url": "https://api.anthropic.com"},
            "secret", session=session,
        )
        self.assertEqual(client.list_models()[0]["id"], "claude-sonnet-x")
        headers = session.request.call_args.kwargs["headers"]
        self.assertEqual(headers["x-api-key"], "secret")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")

    def test_gemini_model_ids_are_normalized(self):
        session = MagicMock()
        session.request.return_value = FakeResponse({
            "models": [
                {"name": "models/gemini-x", "displayName": "Gemini X", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/embedding-x", "supportedGenerationMethods": ["embedContent"]},
            ]
        })
        client = RemoteProviderClient(
            {"provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta"},
            "secret", session=session,
        )
        self.assertEqual(client.list_models(), [{"id": "gemini-x", "name": "Gemini X"}])

    def test_cancel_active_provider_stream_closes_response(self):
        session = MagicMock()
        client = RemoteProviderClient(
            {"provider": "openai", "base_url": "https://api.openai.com/v1"},
            "secret", session=session,
        )
        response = MagicMock()
        client._active_response = response
        client.cancel_chat()
        response.close.assert_called_once()
        client._active_response = None
        client.close()

    def test_provider_cancelled_before_request_starts(self):
        import threading
        session = MagicMock()
        client = RemoteProviderClient(
            {"provider": "openai", "base_url": "https://api.openai.com/v1"},
            "secret", session=session,
        )
        cancel_event = threading.Event()
        cancel_event.set()
        self.assertEqual(
            list(client.chat_stream("gpt-test", [{"role": "user", "content": "hi"}],
                                    cancel_event=cancel_event)),
            [],
        )
        session.request.assert_not_called()
        client.close()

    def test_openai_stream_extracts_delta_text(self):
        session = MagicMock()
        response = FakeResponse(lines=[
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            "data: [DONE]",
        ])
        session.request.return_value = response
        client = RemoteProviderClient(
            {"provider": "openai", "base_url": "https://api.openai.com/v1"},
            "secret", session=session,
        )
        self.assertEqual(
            list(client.chat_stream("gpt-test", [{"role": "user", "content": "hi"}])),
            ["Hello"],
        )
        self.assertEqual(
            session.request.call_args.args[1],
            "https://api.openai.com/v1/chat/completions",
        )

    def test_openai_image_is_serialized_as_data_url(self):
        session = MagicMock()
        session.request.return_value = FakeResponse(lines=["data: [DONE]"])
        client = RemoteProviderClient(
            {"provider": "openai", "base_url": "https://api.openai.com/v1"},
            "secret", session=session,
        )
        messages = [{
            "role": "user", "content": "Describe this.",
            "images": [{"mime_type": "image/png", "data": "aGVsbG8=", "name": "sample.png"}],
        }]
        list(client.chat_stream("gpt-4o", messages))
        payload = session.request.call_args.kwargs["json"]
        image_part = payload["messages"][0]["content"][1]
        self.assertEqual(image_part["type"], "image_url")
        self.assertEqual(image_part["image_url"]["url"], "data:image/png;base64,aGVsbG8=")

    def test_anthropic_stream_extracts_text_delta(self):
        session = MagicMock()
        session.request.return_value = FakeResponse(lines=[
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Claude"}}',
        ])
        client = RemoteProviderClient(
            {"provider": "anthropic", "base_url": "https://api.anthropic.com"},
            "secret", session=session,
        )
        self.assertEqual(
            list(client.chat_stream("claude-test", [{"role": "user", "content": "hi"}])),
            ["Claude"],
        )
        self.assertEqual(session.request.call_args.args[1], "https://api.anthropic.com/v1/messages")

    def test_anthropic_image_is_serialized_as_base64_block(self):
        session = MagicMock()
        session.request.return_value = FakeResponse(lines=[])
        client = RemoteProviderClient(
            {"provider": "anthropic", "base_url": "https://api.anthropic.com"},
            "secret", session=session,
        )
        messages = [{
            "role": "user", "content": "Describe this.",
            "images": [{"mime_type": "image/jpeg", "data": "aGVsbG8=", "name": "sample.jpg"}],
        }]
        list(client.chat_stream("claude-sonnet-x", messages))
        payload = session.request.call_args.kwargs["json"]
        image_part = payload["messages"][0]["content"][1]
        self.assertEqual(image_part["type"], "image")
        self.assertEqual(image_part["source"]["media_type"], "image/jpeg")
        self.assertEqual(image_part["source"]["data"], "aGVsbG8=")

    def test_gemini_stream_extracts_text(self):
        session = MagicMock()
        session.request.return_value = FakeResponse(lines=[
            'data: {"candidates":[{"content":{"parts":[{"text":"Gemini"}]}}]}',
        ])
        client = RemoteProviderClient(
            {"provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta"},
            "secret", session=session,
        )
        self.assertEqual(
            list(client.chat_stream("gemini-test", [{"role": "user", "content": "hi"}])),
            ["Gemini"],
        )

    def test_gemini_image_is_serialized_as_inline_data(self):
        session = MagicMock()
        session.request.return_value = FakeResponse(lines=[])
        client = RemoteProviderClient(
            {"provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta"},
            "secret", session=session,
        )
        messages = [{
            "role": "user", "content": "Describe this.",
            "images": [{"mime_type": "image/webp", "data": "aGVsbG8=", "name": "sample.webp"}],
        }]
        list(client.chat_stream("gemini-test", messages))
        payload = session.request.call_args.kwargs["json"]
        image_part = payload["contents"][0]["parts"][1]["inlineData"]
        self.assertEqual(image_part["mimeType"], "image/webp")
        self.assertEqual(image_part["data"], "aGVsbG8=")

    def test_api_key_is_required_for_official_providers(self):
        with self.assertRaises(ProviderError):
            RemoteProviderClient({"provider": "anthropic", "base_url": "https://api.anthropic.com"})

    def test_api_errors_are_reported(self):
        session = MagicMock()
        session.request.return_value = FakeResponse(
            {"error": {"message": "Invalid API key"}}, status=401
        )
        client = RemoteProviderClient(
            {"provider": "openai", "base_url": "https://api.openai.com/v1"},
            "bad", session=session,
        )
        with self.assertRaisesRegex(ProviderError, "Invalid API key"):
            client.list_models()


if __name__ == "__main__":
    unittest.main()
