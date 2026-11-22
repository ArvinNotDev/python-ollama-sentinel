"""Normalize Ollama's advertised thinking controls for the chat UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ThinkingControls:
    supported: bool
    required: bool
    values: tuple[bool | str, ...]
    default: bool | str | None

    @property
    def levels(self) -> tuple[str, ...]:
        return tuple(value for value in self.values if isinstance(value, str))


def resolve_thinking_controls(model_details: dict[str, Any]) -> ThinkingControls:
    """Interpret /api/show metadata without pretending optional thinking is mandatory.

    Ollama uses boolean values for an on/off switch and string values for named
    thinking levels. When false is not advertised, the UI must keep thinking on.
    """
    capabilities = {
        str(value).strip().lower()
        for value in model_details.get("capabilities", [])
    }
    metadata = model_details.get("thinking")
    raw_values = metadata.get("values", []) if isinstance(metadata, dict) else []
    if not isinstance(raw_values, (list, tuple)):
        raw_values = []
    values = tuple(
        value for value in raw_values
        if isinstance(value, bool) or (isinstance(value, str) and bool(value.strip()))
    )
    if not values and "thinking" in capabilities:
        values = (True,)

    supported = any(
        value is True or (isinstance(value, str) and bool(value.strip()))
        for value in values
    )
    required = supported and False not in values
    default = metadata.get("default") if isinstance(metadata, dict) else None
    if not isinstance(default, (bool, str)):
        default = None
    return ThinkingControls(supported, required, values, default)
