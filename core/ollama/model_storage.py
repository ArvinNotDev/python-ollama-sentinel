"""Safe relocation of an Ollama model directory."""

from __future__ import annotations

import shutil
from pathlib import Path


def move_model_directory(source: str | Path, destination: str | Path) -> Path:
    """Move an Ollama models folder without merging or overwriting another folder."""
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()

    if source_path == destination_path:
        raise ValueError("The new model folder must be different from the current folder.")
    if not source_path.is_dir():
        raise FileNotFoundError(f"The current model folder does not exist: {source_path}")
    if source_path in destination_path.parents or destination_path in source_path.parents:
        raise ValueError("The source and destination folders cannot contain one another.")
    if destination_path.exists():
        if not destination_path.is_dir():
            raise FileExistsError(f"The destination already exists and is not a folder: {destination_path}")
        if any(destination_path.iterdir()):
            raise FileExistsError(f"The destination folder is not empty: {destination_path}")
        destination_path.rmdir()

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(destination_path))
    if not destination_path.is_dir():
        raise OSError("The model folder could not be moved to the requested destination.")
    return destination_path
