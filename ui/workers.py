from __future__ import annotations

from pathlib import Path
import threading
from typing import Any
from urllib.parse import urlparse

from PySide6.QtCore import QThread, Signal

from core.ollama.ollama_commands import OllamaClient
from core.ollama.library import OllamaLibraryClient
from core.ollama.model_storage import move_model_directory
from core.providers import RemoteProviderClient
from core.speech.whisper_manager import WhisperModelManager


class PullWorker(QThread):
    progress = Signal(dict)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, endpoint: str, model_name: str, parent=None) -> None:
        super().__init__(parent)
        self.endpoint = endpoint
        self.model_name = model_name
        self._cancel_event = threading.Event()
        self._client: OllamaClient | None = None
        self._client_lock = threading.Lock()

    def cancel(self) -> None:
        """Stop the active HTTP pull stream; Ollama can resume it on a later pull."""
        self._cancel_event.set()
        with self._client_lock:
            client = self._client
        if client is not None:
            client.cancel_pull()

    def run(self) -> None:
        client: OllamaClient | None = None
        try:
            client = OllamaClient(self.endpoint, timeout=20)
            with self._client_lock:
                self._client = client
            for event in client.pull_model(self.model_name, cancel_event=self._cancel_event):
                if self._cancel_event.is_set():
                    break
                self.progress.emit(event)
            if self._cancel_event.is_set():
                self.cancelled.emit(self.model_name)
            else:
                self.completed.emit(self.model_name)
        except Exception as exc:
            if self._cancel_event.is_set():
                self.cancelled.emit(self.model_name)
            else:
                self.failed.emit(str(exc))
        finally:
            with self._client_lock:
                self._client = None
            if client is not None:
                client.close()


class OllamaCatalogWorker(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def run(self) -> None:
        client = OllamaLibraryClient()
        try:
            self.loaded.emit(client.list_models())
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            client.close()


class OllamaModelTagsWorker(QThread):
    loaded = Signal(str, list)
    failed = Signal(str, str)

    def __init__(self, model_name: str, parent=None) -> None:
        super().__init__(parent)
        self.model_name = model_name

    def run(self) -> None:
        client = OllamaLibraryClient()
        try:
            self.loaded.emit(self.model_name, client.list_tags(self.model_name))
        except Exception as exc:
            self.failed.emit(self.model_name, str(exc))
        finally:
            client.close()


class ChatWorker(QThread):
    chunk = Signal(str)
    thinking_chunk = Signal(str)
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(
        self, endpoint: str, model_name: str, messages: list[dict[str, Any]],
        temperature: float, remote_profile: dict[str, Any] | None = None,
        api_key: str = "", think: bool | str | None = None,
    ) -> None:
        super().__init__()
        self.endpoint = endpoint
        self.model_name = model_name
        self.messages = messages
        self.temperature = temperature
        self.remote_profile = remote_profile
        self.api_key = api_key
        self.think = think

    def run(self) -> None:
        final_event: dict[str, Any] = {}
        try:
            if self.remote_profile:
                client = RemoteProviderClient(self.remote_profile, self.api_key, timeout=30)
                try:
                    for content in client.chat_stream(self.model_name, self.messages, self.temperature):
                        if content:
                            self.chunk.emit(content)
                    self.completed.emit(final_event)
                finally:
                    client.close()
                return
            ollama_messages = []
            for message in self.messages:
                item = {"role": message.get("role", "user"), "content": message.get("content", "")}
                images = message.get("images") or []
                if images:
                    item["images"] = [image.get("data", "") if isinstance(image, dict) else image for image in images]
                ollama_messages.append(item)
            client = OllamaClient(self.endpoint, timeout=30)
            try:
                for event in client.chat_stream(
                    self.model_name, ollama_messages,
                    {"temperature": self.temperature}, think=self.think,
                ):
                    message = event.get("message", {}) or {}
                    thinking = message.get("thinking", "")
                    content = message.get("content", "")
                    if thinking:
                        self.thinking_chunk.emit(thinking)
                    if content:
                        self.chunk.emit(content)
                    if event.get("done"):
                        final_event = event
                self.completed.emit(final_event)
            finally:
                client.close()
        except Exception as exc:
            self.failed.emit(str(exc))


class ModelCapabilitiesWorker(QThread):
    loaded = Signal(str, dict)
    failed = Signal(str, str)

    def __init__(self, endpoint: str, model_name: str, parent=None) -> None:
        super().__init__(parent)
        self.endpoint = endpoint
        self.model_name = model_name

    def run(self) -> None:
        client = OllamaClient(self.endpoint, timeout=12)
        try:
            self.loaded.emit(self.model_name, client.show_model(self.model_name))
        except Exception as exc:
            self.failed.emit(self.model_name, str(exc))
        finally:
            client.close()


class ModelListWorker(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, endpoint: str) -> None:
        super().__init__()
        self.endpoint = endpoint

    def run(self) -> None:
        try:
            client = OllamaClient(self.endpoint, timeout=8)
            try:
                self.loaded.emit(client.list_models())
            finally:
                client.close()
        except Exception as exc:
            self.failed.emit(str(exc))


class DeleteModelWorker(QThread):
    completed = Signal()
    failed = Signal(str)

    def __init__(self, endpoint: str, model_name: str, parent=None) -> None:
        super().__init__(parent)
        self.endpoint = endpoint
        self.model_name = model_name

    def run(self) -> None:
        try:
            client = OllamaClient(self.endpoint, timeout=20)
            try:
                client.delete_model(self.model_name)
                self.completed.emit()
            finally:
                client.close()
        except Exception as exc:
            self.failed.emit(str(exc))


class MoveOllamaModelsWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, source: str, destination: str, endpoint: str, parent=None) -> None:
        super().__init__(parent)
        self.source = source
        self.destination = destination
        self.endpoint = endpoint

    def run(self) -> None:
        client = None
        try:
            parsed = urlparse(self.endpoint)
            if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
                client = OllamaClient(self.endpoint, timeout=1.5)
                if client.is_available(timeout=1.0):
                    raise RuntimeError(
                        "Ollama is still running. Stop the local Ollama server completely, then retry Move Models."
                    )
            destination = move_model_directory(self.source, self.destination)
            self.completed.emit(str(destination))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if client is not None:
                client.close()


class ProviderModelsWorker(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, profile: dict[str, Any], api_key: str) -> None:
        super().__init__()
        self.profile = profile
        self.api_key = api_key

    def run(self) -> None:
        try:
            client = RemoteProviderClient(self.profile, self.api_key, timeout=15)
            try:
                self.loaded.emit(client.list_models())
            finally:
                client.close()
        except Exception as exc:
            self.failed.emit(str(exc))


class WhisperDownloadWorker(QThread):
    progress = Signal(int, int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, manager: WhisperModelManager, model_name: str, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.model_name = model_name

    def run(self) -> None:
        try:
            path = self.manager.download_model(
                self.model_name,
                progress_callback=lambda current, total: self.progress.emit(current, total),
            )
            self.completed.emit(str(path))
        except Exception as exc:
            self.failed.emit(str(exc))


class WhisperTranscriptionWorker(QThread):
    completed = Signal(str, str)
    failed = Signal(str)

    def __init__(
        self, manager: WhisperModelManager, audio_path: str,
        model_name: str = "base", language: str | None = None, parent=None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager
        self.audio_path = audio_path
        self.model_name = model_name
        self.language = language

    def run(self) -> None:
        try:
            text, detected_language = self.manager.transcribe(
                self.audio_path, self.model_name, self.language
            )
            if not text:
                raise RuntimeError("No speech was recognized. Try speaking closer to the microphone.")
            self.completed.emit(text, detected_language)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            Path(self.audio_path).unlink(missing_ok=True)
