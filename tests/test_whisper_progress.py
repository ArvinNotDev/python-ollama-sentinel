import unittest

from core.speech.whisper_manager import _ProgressTqdm


class WhisperProgressTests(unittest.TestCase):
    def test_progress_bar_accepts_huggingface_named_progress_argument(self):
        updates = []
        previous = _ProgressTqdm.callback
        _ProgressTqdm.callback = lambda current, total: updates.append((current, total))
        try:
            progress = _ProgressTqdm(
                total=10,
                name="huggingface_hub.snapshot_download",
                disable=True,
            )
            progress.update(4)
            progress.close()
        finally:
            _ProgressTqdm.callback = previous

        self.assertEqual(updates, [(4, 10)])


if __name__ == "__main__":
    unittest.main()
