"""Download and run multilingual Whisper models entirely on the local machine."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Callable

from tqdm.auto import tqdm


WHISPER_MODELS = {
    "tiny": {
        "repo_id": "Systran/faster-whisper-tiny",
        "description": "Fastest and lightest · useful for quick voice input",
    },
    "base": {
        "repo_id": "Systran/faster-whisper-base",
        "description": "Balanced starting point · multilingual including Persian",
    },
    "small": {
        "repo_id": "Systran/faster-whisper-small",
        "description": "Better recognition quality · needs more memory",
    },
    "medium": {
        "repo_id": "Systran/faster-whisper-medium",
        "description": "Higher accuracy · slower and memory intensive",
    },
    "large-v3": {
        "repo_id": "Systran/faster-whisper-large-v3",
        "description": "High accuracy multilingual model · resource intensive",
    },
    "large-v3-turbo": {
        "repo_id": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "description": "Fast large-v3 turbo checkpoint · multilingual transcription",
    },
    "distil-large-v3": {
        "repo_id": "Systran/faster-distil-whisper-large-v3",
        "description": "Distilled large-v3 with faster decoding and multilingual coverage",
    },
}


_DOWNLOAD_LOCK = threading.Lock()


class _ProgressTqdm(tqdm):
    callback: Callable[[int, int], None] | None = None

    def update(self, n=1):
        result = super().update(n)
        callback = type(self).callback
        if callback and self.total and self.total > 0:
            callback(int(self.n), int(self.total))
        return result


class WhisperModelManager:
    def __init__(self, models_directory: str | Path) -> None:
        self.set_models_directory(models_directory)
        self._loaded_models: dict[str, object] = {}
        self._model_lock = threading.RLock()

    def set_models_directory(self, models_directory: str | Path) -> None:
        new_directory = Path(models_directory).expanduser()
        previous_directory = getattr(self, "models_directory", None)
        self.models_directory = new_directory
        if previous_directory is not None and previous_directory != new_directory:
            lock = getattr(self, "_model_lock", None)
            if lock is not None:
                with lock:
                    self._loaded_models.clear()

    def model_path(self, model_name: str) -> Path:
        if model_name not in WHISPER_MODELS:
            raise ValueError(f"Unknown Whisper model: {model_name}")
        return self.models_directory / model_name

    def is_installed(self, model_name: str) -> bool:
        path = self.model_path(model_name)
        return (
            (path / "model.bin").is_file()
            and (path / "config.json").is_file()
            and (path / "tokenizer.json").is_file()
        )

    def installed_models(self) -> list[str]:
        return [name for name in WHISPER_MODELS if self.is_installed(name)]

    def download_model(
        self,
        model_name: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Path:
        if model_name not in WHISPER_MODELS:
            raise ValueError(f"Unknown Whisper model: {model_name}")
        if not _DOWNLOAD_LOCK.acquire(blocking=False):
            raise RuntimeError("Another Whisper model download is already running.")
        try:
            target = self.model_path(model_name)
            target.mkdir(parents=True, exist_ok=True)
            from huggingface_hub import snapshot_download

            _ProgressTqdm.callback = progress_callback
            try:
                snapshot_download(
                    repo_id=WHISPER_MODELS[model_name]["repo_id"],
                    local_dir=str(target),
                    allow_patterns=[
                        "config.json",
                        "preprocessor_config.json",
                        "model.bin",
                        "tokenizer.json",
                        "vocabulary.*",
                    ],
                    max_workers=1,
                    tqdm_class=_ProgressTqdm,
                )
            finally:
                _ProgressTqdm.callback = None
            if not self.is_installed(model_name):
                raise RuntimeError(
                    "The model download finished, but required Whisper files are missing. "
                    "Check the Hugging Face download and try again."
                )
            return target
        finally:
            _ProgressTqdm.callback = None
            _DOWNLOAD_LOCK.release()

    def remove_model(self, model_name: str) -> None:
        path = self.model_path(model_name)
        with self._model_lock:
            self._loaded_models.pop(model_name, None)
        if path.exists():
            shutil.rmtree(path)

    def transcribe(
        self,
        audio_path: str | Path,
        model_name: str = "base",
        language: str | None = None,
    ) -> tuple[str, str]:
        if not self.is_installed(model_name):
            raise RuntimeError(f"Whisper {model_name} is not installed.")
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Speech recognition dependencies are missing. Install requirements.txt and restart the app."
            ) from exc

        with self._model_lock:
            model = self._loaded_models.get(model_name)
            if model is None:
                model = WhisperModel(
                    str(self.model_path(model_name)),
                    device="cpu",
                    compute_type="int8",
                )
                self._loaded_models[model_name] = model

            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                beam_size=3,
                vad_filter=True,
            )
            text_parts = [segment.text.strip() for segment in segments if segment.text.strip()]
            detected_language = getattr(info, "language", "") or language or "unknown"
            return " ".join(text_parts).strip(), detected_language
