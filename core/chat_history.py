"""Persistent storage for complete local chat conversations."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QStandardPaths


class ChatHistoryStore:
    """Store every conversation, including multimodal payloads and reasoning text."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            base = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppLocalDataLocation
            )
            path = Path(base or Path.home() / ".local" / "share" / "ollama-sentinel") / "chats.json"
        self.path = Path(path)
        self.load_warning = ""
        self._preservation_failed = False

    def _preserve_unreadable_history(self, detail: str) -> None:
        try:
            backup = self.path.with_name(
                f"{self.path.name}.corrupt-{uuid.uuid4().hex[:8]}.bak"
            )
            shutil.copy2(self.path, backup)
            self.load_warning = (
                f"Chat history could not be read. The original file was preserved as "
                f"{backup.name}; a new history can now be saved safely."
            )
        except OSError as exc:
            self._preservation_failed = True
            self.load_warning = (
                f"Chat history could not be read or backed up ({detail}; {exc}). "
                "The existing file will not be overwritten."
            )

    def load(self) -> list[dict[str, Any]]:
        """Load all valid conversations without truncating their message history."""
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as exc:
            self._preserve_unreadable_history(str(exc))
            return []
        except OSError as exc:
            self._preservation_failed = True
            self.load_warning = (
                f"Could not read chat history ({exc}). The existing file will not be overwritten."
            )
            return []

        if isinstance(payload, dict):
            if "conversations" not in payload:
                self._preserve_unreadable_history("unsupported history format")
                return []
            conversations = payload["conversations"]
        else:
            # Accept the original list shape too, should a user have an older file.
            conversations = payload

        if not isinstance(conversations, list):
            self._preserve_unreadable_history("unsupported history format")
            return []

        valid: list[dict[str, Any]] = []
        for conversation in conversations:
            if not isinstance(conversation, dict):
                continue
            conversation_id = conversation.get("id")
            messages = conversation.get("messages")
            if not isinstance(conversation_id, str) or not isinstance(messages, list):
                continue
            clean_messages = [
                deepcopy(message)
                for message in messages
                if isinstance(message, dict)
                and message.get("role") in {"user", "assistant", "system"}
                and isinstance(message.get("content", ""), str)
            ]
            valid.append({
                **deepcopy(conversation),
                "id": conversation_id,
                "title": str(conversation.get("title") or "New chat"),
                "messages": clean_messages,
            })
        return valid

    def save(self, conversations: list[dict[str, Any]]) -> None:
        """Atomically replace history after preserving any unreadable original file."""
        if self._preservation_failed:
            raise OSError(self.load_warning or "The existing chat history cannot be safely replaced.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {"version": 1, "conversations": conversations}
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
