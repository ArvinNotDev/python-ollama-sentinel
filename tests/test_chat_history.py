import tempfile
import unittest
from pathlib import Path

from core.chat_history import ChatHistoryStore


class ChatHistoryStoreTests(unittest.TestCase):
    def test_round_trip_preserves_all_messages_images_and_thinking(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ChatHistoryStore(Path(directory) / "chats.json")
            conversations = [{
                "id": "conversation-1",
                "title": "Inspect this image",
                "created_at": "2026-11-23T10:00:00+00:00",
                "updated_at": "2026-11-23T10:05:00+00:00",
                "model_selection": {"source": "ollama", "model_id": "llava"},
                "messages": [
                    {
                        "role": "user",
                        "content": "What is in this picture?",
                        "images": [{
                            "name": "photo.png",
                            "mime_type": "image/png",
                            "data": "c29tZS1iYXNlNjQtZGF0YQ==",
                        }],
                        "attachments": [{"name": "photo.png", "kind": "image"}],
                    },
                    {
                        "role": "assistant",
                        "content": "A landscape.",
                        "thinking": "I should identify the visible objects first.",
                    },
                ],
            }]

            store.save(conversations)

            self.assertEqual(store.load(), conversations)

    def test_history_is_not_truncated_after_many_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ChatHistoryStore(Path(directory) / "chats.json")
            messages = [
                {"role": "user", "content": f"Question {index}"}
                if index % 2 == 0 else {"role": "assistant", "content": f"Answer {index}"}
                for index in range(250)
            ]
            store.save([{"id": "long-chat", "messages": messages}])

            loaded = store.load()

            self.assertEqual(len(loaded[0]["messages"]), 250)
            self.assertEqual(loaded[0]["messages"][-1]["content"], "Answer 249")

    def test_missing_or_corrupt_file_returns_empty_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chats.json"
            store = ChatHistoryStore(path)
            self.assertEqual(store.load(), [])

            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(store.load(), [])

    def test_corrupt_history_is_backed_up_before_new_history_is_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chats.json"
            original = b'{"conversations": [broken'
            path.write_bytes(original)
            store = ChatHistoryStore(path)

            self.assertEqual(store.load(), [])
            backups = list(Path(directory).glob("chats.json.corrupt-*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            self.assertIn(backups[0].name, store.load_warning)

            store.save([{"id": "new-chat", "messages": []}])

            self.assertEqual(store.load()[0]["id"], "new-chat")
            self.assertEqual(backups[0].read_bytes(), original)

    def test_invalid_conversation_entries_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chats.json"
            path.write_text(
                '{"version":1,"conversations":['
                '{"id":"valid","messages":[{"role":"user","content":"Hello"}]},'
                '{"messages":[]},'
                '{"id":"invalid-messages","messages":"not a list"}'
                ']}',
                encoding="utf-8",
            )

            loaded = ChatHistoryStore(path).load()

            self.assertEqual([item["id"] for item in loaded], ["valid"])


if __name__ == "__main__":
    unittest.main()
