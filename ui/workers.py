from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal

from core.ollama.ollama_commands import OllamaClient


class PullWorker(QThread):
    progress = Signal(dict)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, endpoint: str, model_name: str) -> None:
        super().__init__()
        self.endpoint = endpoint
        self.model_name = model_name

    def run(self) -> None:
        try:
            client = OllamaClient(self.endpoint, timeout=20)
            try:
                for event in client.pull_model(self.model_name):
                    self.progress.emit(event)
                    if event.get("status") == "success":
                        self.completed.emit(self.model_name)
                        return
                self.completed.emit(self.model_name)
            finally:
                client.close()
        except Exception as exc:
            self.failed.emit(str(exc))


class ChatWorker(QThread):
    chunk = Signal(str)
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(
        self, endpoint: str, model_name: str, messages: list[dict[str, str]], temperature: float
    ) -> None:
        super().__init__()
        self.endpoint = endpoint
        self.model_name = model_name
        self.messages = messages
        self.temperature = temperature

    def run(self) -> None:
        final_event: dict[str, Any] = {}
        try:
            client = OllamaClient(self.endpoint, timeout=30)
            try:
                for event in client.chat_stream(
                    self.model_name, self.messages, {"temperature": self.temperature}
                ):
                    content = event.get("message", {}).get("content", "")
                    if content:
                        self.chunk.emit(content)
                    if event.get("done"):
                        final_event = event
                self.completed.emit(final_event)
            finally:
                client.close()
        except Exception as exc:
            self.failed.emit(str(exc))


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
