"""Remote model provider adapters (OpenAI-compatible, Anthropic and Gemini)."""

from __future__ import annotations

import json
from typing import Any, Iterator
from urllib.parse import quote

import requests


class ProviderError(RuntimeError):
    """Raised for provider API, authentication or transport failures."""


PROVIDER_DEFAULTS = {
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "requires_key": True,
        "protocol": "openai",
    },
    "anthropic": {
        "label": "Anthropic · Claude",
        "base_url": "https://api.anthropic.com",
        "requires_key": True,
        "protocol": "anthropic",
    },
    "google": {
        "label": "Google · Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "requires_key": True,
        "protocol": "gemini",
    },
    "openai_compatible": {
        "label": "OpenAI-compatible",
        "base_url": "",
        "requires_key": False,
        "protocol": "openai",
    },
}


class RemoteProviderClient:
    def __init__(
        self,
        profile: dict[str, Any],
        api_key: str = "",
        timeout: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        self.profile = dict(profile)
        self.provider = str(self.profile.get("provider", "openai_compatible"))
        if self.provider not in PROVIDER_DEFAULTS:
            raise ProviderError(f"Unsupported provider: {self.provider}")
        defaults = PROVIDER_DEFAULTS[self.provider]
        self.protocol = defaults["protocol"]
        self.base_url = str(self.profile.get("base_url") or defaults["base_url"]).rstrip("/")
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.session = session or requests.Session()
        if not self.base_url.startswith(("http://", "https://")):
            raise ProviderError("Provider URL must start with http:// or https://.")
        if defaults["requires_key"] and not self.api_key:
            raise ProviderError(f"An API key is required for {defaults['label']}.")

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.protocol == "anthropic":
            headers.update({"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
        elif self.protocol == "gemini":
            headers["x-goog-api-key"] = self.api_key
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    @staticmethod
    def _decode_error(response: requests.Response) -> str:
        try:
            payload = response.json()
            error = payload.get("error", payload)
            if isinstance(error, dict):
                return str(error.get("message") or error.get("status") or error)
            return str(error)
        except (ValueError, AttributeError):
            return (getattr(response, "text", "") or "").strip()

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        headers = self._headers()
        headers.update(kwargs.pop("headers", {}))
        try:
            response = self.session.request(
                method, f"{self.base_url}{path}", headers=headers,
                timeout=kwargs.pop("timeout", self.timeout), **kwargs,
            )
            if not response.ok:
                detail = self._decode_error(response)
                raise ProviderError(detail or f"Provider returned HTTP {response.status_code}.")
            return response
        except requests.RequestException as exc:
            response = getattr(exc, "response", None)
            detail = self._decode_error(response) if response is not None else ""
            raise ProviderError(detail or f"Could not reach the provider: {exc}") from exc

    def list_models(self) -> list[dict[str, str]]:
        path = "/v1/models" if self.protocol == "anthropic" else "/models"
        response = self._request("GET", path)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("Provider returned an invalid model-list response.") from exc
        raw_models = payload.get("data") or payload.get("models") or []
        models: list[dict[str, str]] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or item.get("name") or "").strip()
            if not model_id:
                continue
            if self.protocol == "gemini":
                methods = item.get("supportedGenerationMethods") or []
                if methods and "generateContent" not in methods:
                    continue
                model_id = model_id.removeprefix("models/")
            display = str(item.get("display_name") or item.get("displayName") or model_id)
            models.append({"id": model_id, "name": display})
        return models

    @staticmethod
    def _sse_data(response: requests.Response) -> Iterator[dict[str, Any]]:
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                if event.get("error"):
                    error = event["error"]
                    if isinstance(error, dict):
                        error = error.get("message") or error
                    raise ProviderError(str(error))
                yield event

    def chat_stream(self, model: str, messages: list[dict[str, Any]], temperature: float = 0.7) -> Iterator[str]:
        if self.protocol == "anthropic":
            yield from self._chat_anthropic(model, messages, temperature)
        elif self.protocol == "gemini":
            yield from self._chat_gemini(model, messages, temperature)
        else:
            yield from self._chat_openai(model, messages, temperature)

    @staticmethod
    def _openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for message in messages:
            item: dict[str, Any] = {
                "role": message.get("role", "user"),
                "content": message.get("content", ""),
            }
            images = message.get("images") or []
            if images:
                parts = []
                if item["content"]:
                    parts.append({"type": "text", "text": item["content"]})
                for image in images:
                    parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f'data:{image["mime_type"]};base64,{image["data"]}',
                            "detail": "auto",
                        },
                    })
                item["content"] = parts
            result.append(item)
        return result

    def _chat_openai(self, model: str, messages: list[dict[str, Any]], temperature: float) -> Iterator[str]:
        response = self._request(
            "POST", "/chat/completions",
            json={"model": model, "messages": self._openai_messages(messages), "temperature": temperature, "stream": True},
            stream=True, timeout=(10, None), headers={"Content-Type": "application/json"},
        )
        with response:
            for event in self._sse_data(response):
                for choice in event.get("choices") or []:
                    content = (choice.get("delta") or {}).get("content")
                    if isinstance(content, str) and content:
                        yield content
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and isinstance(part.get("text"), str):
                                yield part["text"]

    def _chat_anthropic(self, model: str, messages: list[dict[str, Any]], temperature: float) -> Iterator[str]:
        system_parts = [item["content"] for item in messages if item.get("role") == "system"]
        conversation = []
        for item in messages:
            if item.get("role") == "system":
                continue
            content: Any = item.get("content", "")
            images = item.get("images") or []
            if images:
                blocks = [{"type": "text", "text": content}] if content else []
                for image in images:
                    blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image["mime_type"],
                            "data": image["data"],
                        },
                    })
                content = blocks
            conversation.append({"role": item.get("role", "user"), "content": content})
        body: dict[str, Any] = {
            "model": model, "max_tokens": 4096, "messages": conversation,
            "stream": True, "temperature": temperature,
        }
        if system_parts:
            body["system"] = "\n\n".join(system_parts)
        response = self._request(
            "POST", "/v1/messages", json=body, stream=True, timeout=(10, None),
            headers={"Content-Type": "application/json"},
        )
        with response:
            for event in self._sse_data(response):
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta") or {}
                    if delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
                        yield delta["text"]

    def _chat_gemini(self, model: str, messages: list[dict[str, Any]], temperature: float) -> Iterator[str]:
        system_parts = [item["content"] for item in messages if item.get("role") == "system"]
        conversation = []
        for item in messages:
            if item.get("role") == "system":
                continue
            parts = [{"text": item.get("content", "")}] if item.get("content") else []
            for image in item.get("images") or []:
                parts.append({
                    "inlineData": {
                        "mimeType": image["mime_type"],
                        "data": image["data"],
                    }
                })
            conversation.append({
                "role": "model" if item.get("role") == "assistant" else "user",
                "parts": parts,
            })
        body: dict[str, Any] = {
            "contents": conversation, "generationConfig": {"temperature": temperature},
        }
        if system_parts:
            body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        response = self._request(
            "POST", f"/models/{quote(model, safe='')}:streamGenerateContent?alt=sse",
            json=body, stream=True, timeout=(10, None),
            headers={"Content-Type": "application/json"},
        )
        with response:
            for event in self._sse_data(response):
                for candidate in event.get("candidates") or []:
                    content = candidate.get("content") or {}
                    for part in content.get("parts") or []:
                        if isinstance(part.get("text"), str):
                            yield part["text"]

    def close(self) -> None:
        self.session.close()
