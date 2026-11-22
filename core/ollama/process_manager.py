"""Optional app-managed Ollama server process."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from core.ollama.ollama_commands import OllamaClient


class OllamaProcessManager:
    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None

    @staticmethod
    def find_executable(configured_path: str = "") -> str | None:
        if configured_path and Path(configured_path).is_file():
            return configured_path
        found = shutil.which("ollama")
        if found:
            return found
        if os.name == "nt":
            candidates = [
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
                Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Ollama" / "ollama.exe",
            ]
            for candidate in candidates:
                if candidate.is_file():
                    return str(candidate)
        return None

    def start(self, models_directory: str, endpoint: str, executable: str = "") -> tuple[bool, str]:
        try:
            parsed_endpoint = urlparse(endpoint)
            host = parsed_endpoint.hostname
            port = parsed_endpoint.port
        except ValueError:
            return False, "Enter a valid local Ollama address before starting the managed server."
        if parsed_endpoint.scheme != "http" or host not in {"localhost", "127.0.0.1", "::1"}:
            return False, "The app-managed Ollama process can only bind to a local HTTP address (localhost or 127.0.0.1). Remote endpoints can still be used for chat and downloads."
        client = OllamaClient(endpoint, timeout=1.0)
        available = client.is_available(timeout=0.8)
        client.close()
        if available:
            return False, "An Ollama server is already responding at this address. Stop it before launching another server with a different model folder."
        if self.process and self.process.poll() is None:
            return False, "The Ollama server launched by this app is already running."
        binary = self.find_executable(executable)
        if not binary:
            return False, "Ollama executable was not found. Install Ollama or select ollama.exe in Settings."
        folder = Path(models_directory).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return False, f"Cannot create the model folder: {exc}"
        env = os.environ.copy()
        env["OLLAMA_MODELS"] = str(folder.resolve())
        bind_host = f"[{host}]" if ":" in host else host
        env["OLLAMA_HOST"] = f"{bind_host}:{port or 11434}"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            self.process = subprocess.Popen(
                [binary, "serve"], env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except OSError as exc:
            return False, f"Could not launch Ollama: {exc}"
        return True, "Ollama is starting with the selected model directory."

    def stop(self) -> None:
        if not self.process or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
        self.process = None
