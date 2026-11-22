"""Small, versioned JSON settings store for Ollama Sentinel."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths


DEFAULT_ENDPOINT = "http://127.0.0.1:11434"


class SettingsStore:
    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
            path = Path(base or Path.home() / ".config" / "ollama-sentinel") / "settings.json"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {
            "version": 1,
            "endpoint": DEFAULT_ENDPOINT,
            "models_directory": str(Path.home() / ".ollama" / "models"),
            "ollama_executable": "",
            "temperature": 0.7,
        }
        self._load()

    def _load(self) -> None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._data.update(loaded)
        except (OSError, json.JSONDecodeError):
            self.save()

    def save(self) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self.path)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    @property
    def endpoint(self) -> str:
        return str(self.get("endpoint", DEFAULT_ENDPOINT)).rstrip("/")

    @property
    def models_directory(self) -> str:
        return str(self.get("models_directory", ""))

    @property
    def ollama_executable(self) -> str:
        return str(self.get("ollama_executable", ""))
