"""Persistent, non-secret application settings and provider profiles."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths

from core.secrets import SecretStore


DEFAULT_ENDPOINT = "http://127.0.0.1:11434"


class SettingsStore:
    def __init__(self, path: str | Path | None = None, secret_store: SecretStore | None = None) -> None:
        if path is None:
            base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
            path = Path(base or Path.home() / ".config" / "ollama-sentinel") / "settings.json"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        local_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        default_speech_dir = Path(local_data or Path.home() / ".local" / "share" / "ollama-sentinel") / "speech-models"
        self.secret_store = secret_store or SecretStore()
        self._data: dict[str, Any] = {
            "version": 3,
            "endpoint": DEFAULT_ENDPOINT,
            "models_directory": str(Path.home() / ".ollama" / "models"),
            "ollama_executable": "",
            "temperature": 0.7,
            "api_profiles": [],
            "speech_models_directory": str(default_speech_dir),
            "speech_default_model": "base",
            "speech_language": "auto",
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

    @property
    def speech_models_directory(self) -> str:
        return str(self.get("speech_models_directory", ""))

    @property
    def speech_default_model(self) -> str:
        return str(self.get("speech_default_model", "base"))

    @property
    def speech_language(self) -> str:
        return str(self.get("speech_language", "auto"))

    def list_api_profiles(self) -> list[dict[str, Any]]:
        return [dict(profile) for profile in self.get("api_profiles", [])]

    def get_api_profile(self, profile_id: str) -> dict[str, Any] | None:
        for profile in self.list_api_profiles():
            if profile.get("id") == profile_id:
                return profile
        return None

    def save_api_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        clean = {
            "id": str(profile.get("id") or uuid.uuid4()),
            "name": str(profile.get("name", "")).strip(),
            "provider": str(profile.get("provider", "openai_compatible")),
            "base_url": str(profile.get("base_url", "")).strip().rstrip("/"),
            "models": [
                {"id": str(item.get("id", "")).strip(), "name": str(item.get("name") or item.get("id", "")).strip()}
                for item in profile.get("models", [])
                if isinstance(item, dict) and str(item.get("id", "")).strip()
            ],
        }
        profiles = self.list_api_profiles()
        for index, existing in enumerate(profiles):
            if existing.get("id") == clean["id"]:
                profiles[index] = clean
                break
        else:
            profiles.append(clean)
        self.set("api_profiles", profiles)
        return clean

    def delete_api_profile(self, profile_id: str) -> None:
        profiles = [profile for profile in self.list_api_profiles() if profile.get("id") != profile_id]
        self.set("api_profiles", profiles)
        self.secret_store.delete(profile_id)

    def get_api_key(self, profile_id: str) -> str:
        return self.secret_store.get(profile_id)

    def set_api_key(self, profile_id: str, api_key: str) -> None:
        if api_key:
            self.secret_store.set(profile_id, api_key)
