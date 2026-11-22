import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.settings import SettingsStore


class SettingsProviderTests(unittest.TestCase):
    def test_provider_profiles_are_saved_without_api_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            secret_store = MagicMock()
            settings_path = Path(directory) / "settings.json"
            settings = SettingsStore(settings_path, secret_store=secret_store)
            profile = settings.save_api_profile({
                "id": "profile-1",
                "name": "Work OpenAI",
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "models": [{"id": "gpt-test"}],
            })
            settings.set_api_key(profile["id"], "never-write-this")
            raw_text = settings_path.read_text(encoding="utf-8")
            raw = json.loads(raw_text)
            self.assertNotIn("never-write-this", raw_text)
            self.assertEqual(raw["api_profiles"][0]["models"][0]["id"], "gpt-test")
            secret_store.set.assert_called_once_with("profile-1", "never-write-this")


if __name__ == "__main__":
    unittest.main()
