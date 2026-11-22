"""OS-backed credential storage. API keys are never written to settings.json."""

from __future__ import annotations

import keyring
from keyring.errors import KeyringError


SERVICE_NAME = "Ollama Sentinel"


class SecretStoreError(RuntimeError):
    pass


class SecretStore:
    def get(self, profile_id: str) -> str:
        try:
            return keyring.get_password(SERVICE_NAME, profile_id) or ""
        except (KeyringError, RuntimeError) as exc:
            raise SecretStoreError(
                "The operating system credential store is unavailable. Configure Windows Credential Manager, macOS Keychain or a supported Linux Secret Service."
            ) from exc

    def set(self, profile_id: str, secret: str) -> None:
        try:
            keyring.set_password(SERVICE_NAME, profile_id, secret)
        except (KeyringError, RuntimeError) as exc:
            raise SecretStoreError(
                "Could not save the API key to the operating system credential store. No key was written to the app settings file."
            ) from exc

    def delete(self, profile_id: str) -> None:
        try:
            keyring.delete_password(SERVICE_NAME, profile_id)
        except keyring.errors.PasswordDeleteError:
            return
        except (KeyringError, RuntimeError) as exc:
            raise SecretStoreError("Could not remove the API key from the operating system credential store.") from exc
