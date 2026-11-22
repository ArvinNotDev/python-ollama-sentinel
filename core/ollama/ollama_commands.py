"""A small, explicit REST client for the local Ollama HTTP API."""

from __future__ import annotations

import json
from typing import Any, Iterator
from urllib.parse import urlparse

import requests


class OllamaError(RuntimeError):
    """Raised when Ollama returns an API or transport error."""


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        try:
            parsed = urlparse(self.base_url)
            valid_host = bool(parsed.hostname)
        except ValueError as exc:
            raise ValueError("Ollama address must be a valid HTTP or HTTPS URL.") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or not valid_host:
            raise ValueError("Ollama address must be a valid HTTP or HTTPS URL.")

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url}{endpoint}"

    @staticmethod
    def _raise_for_api_error(payload: dict[str, Any]) -> None:
        if payload.get("error"):
            raise OllamaError(str(payload["error"]))

    def is_available(self, timeout: float = 1.5) -> bool:
        try:
            response = self.session.get(self._url("/api/tags"), timeout=timeout)
            return response.ok
        except requests.RequestException:
            return False

    def list_models(self) -> list[dict[str, Any]]:
        try:
            response = self.session.get(self._url("/api/tags"), timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            return payload.get("models", [])
        except (requests.RequestException, ValueError) as exc:
            raise OllamaError(f"Could not load installed models: {exc}") from exc

    def show_model(self, model_name: str) -> dict[str, Any]:
        try:
            response = self.session.post(
                self._url("/api/show"), json={"model": model_name}, timeout=self.timeout
            )
            response.raise_for_status()
            payload = response.json()
            self._raise_for_api_error(payload)
            return payload
        except (requests.RequestException, ValueError) as exc:
            raise OllamaError(f"Could not inspect {model_name}: {exc}") from exc

    def pull_model(
        self, model_name: str, cancel_event: threading.Event | None = None
    ) -> Iterator[dict[str, Any]]:
        """Yield Ollama pull events; closing the active response stops the current pull."""
        if cancel_event is not None and cancel_event.is_set():
            return
        try:
            with self.session.post(
                self._url("/api/pull"),
                json={"name": model_name, "stream": True},
                stream=True,
                timeout=(10, None),
            ) as response:
                with self._pull_response_lock:
                    self._pull_response = response
                try:
                    response.raise_for_status()
                    for line in response.iter_lines(decode_unicode=True):
                        if cancel_event is not None and cancel_event.is_set():
                            return
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                        except (TypeError, json.JSONDecodeError) as exc:
                            raise OllamaError("Ollama returned an invalid download progress event.") from exc
                        self._raise_for_api_error(event)
                        yield event
                finally:
                    with self._pull_response_lock:
                        self._pull_response = None
        except requests.RequestException as exc:
            if cancel_event is not None and cancel_event.is_set():
                return
            detail = getattr(exc.response, "text", "") if getattr(exc, "response", None) else ""
            raise OllamaError(detail.strip() or f"Download failed: {exc}") from exc

    def cancel_pull(self) -> None:
        """Close the active streaming response to interrupt a pull request."""
        with self._pull_response_lock:
            response = self._pull_response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def delete_model(self, model_name: str) -> None:
        try:
            response = self.session.request(
                "DELETE", self._url("/api/delete"), json={"model": model_name}, timeout=self.timeout
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaError(f"Could not remove {model_name}: {exc}") from exc

    def chat_stream(
        self, model_name: str, messages: list[dict[str, str]], options: dict[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        body: dict[str, Any] = {"model": model_name, "messages": messages, "stream": True}
        if options:
            body["options"] = options
        try:
            with self.session.post(
                self._url("/api/chat"), json=body, stream=True, timeout=(10, None)
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except (TypeError, json.JSONDecodeError) as exc:
                        raise OllamaError("Ollama returned an invalid chat response.") from exc
                    self._raise_for_api_error(event)
                    yield event
        except requests.RequestException as exc:
            detail = getattr(exc.response, "text", "") if getattr(exc, "response", None) else ""
            raise OllamaError(detail.strip() or f"Could not generate a response: {exc}") from exc

    def close(self) -> None:
        self.session.close()


class OllamaUtils:
    """Compatibility facade for the original synchronous helper API."""

    @classmethod
    def list_downloaded_models(cls):
        client = OllamaClient()
        try:
            return client.list_models()
        except OllamaError:
            return []
        finally:
            client.close()

    @classmethod
    def pull_model(cls, model_name: str) -> bool:
        client = OllamaClient()
        try:
            for _event in client.pull_model(model_name):
                pass
            return True
        except OllamaError:
            return False
        finally:
            client.close()

    @classmethod
    def send_message_to_model(cls, model_name: str, prompt: str, history: list):
        messages = list(history) + [{"role": "user", "content": prompt}]
        client = OllamaClient()
        try:
            chunks = []
            for event in client.chat_stream(model_name, messages):
                chunks.append(event.get("message", {}).get("content", ""))
            history.append({"role": "user", "content": prompt})
            answer = "".join(chunks)
            history.append({"role": "assistant", "content": answer})
            return answer
        except OllamaError:
            return None
        finally:
            client.close()
