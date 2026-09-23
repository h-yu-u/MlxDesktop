import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "services" / "runtime" / "src"))

from mlx_studio_runtime.adapters.persistence.sqlite_store import SQLiteStore
from mlx_studio_runtime.domain.models import fake_text_manifest, manifest_from_dict


class SQLiteStoreTests(unittest.TestCase):
    def test_attachment_order_and_model_manifest_survive_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "app.db"
            store = SQLiteStore(database)
            store.save_conversation({"id": "conversation-1", "title": "Test"})
            for attachment_id in ("image-2", "image-1"):
                store.save_attachment(
                    {
                        "id": attachment_id,
                        "sha256": attachment_id,
                        "mimeType": "image/png",
                        "sizeBytes": 8,
                        "relativePath": f"attachments/{attachment_id}",
                        "originalName": f"{attachment_id}.png",
                    }
                )
            store.save_message(
                {
                    "id": "message-1",
                    "conversationId": "conversation-1",
                    "role": "user",
                    "content": "look",
                    "attachmentIds": ["image-2", "image-1"],
                }
            )
            manifest = fake_text_manifest()
            store.upsert_model(manifest.to_dict())
            store.close()

            reopened = SQLiteStore(database)
            conversation = reopened.get_conversation("conversation-1")
            self.assertEqual(
                [item["id"] for item in conversation["messages"][0]["attachments"]],
                ["image-2", "image-1"],
            )
            restored = manifest_from_dict(reopened.list_models()[0])
            self.assertEqual(restored.id, manifest.id)
            reopened.close()

    def test_conversation_and_messages_survive_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "data" / "app.db"
            store = SQLiteStore(database)
            store.save_conversation(
                {"id": "conversation-1", "title": "Test", "modelId": "model-1"}
            )
            store.save_message(
                {
                    "id": "message-1",
                    "conversationId": "conversation-1",
                    "role": "user",
                    "content": "hello",
                }
            )
            store.close()

            reopened = SQLiteStore(database)
            conversation = reopened.get_conversation("conversation-1")
            self.assertIsNotNone(conversation)
            self.assertEqual(conversation["messages"][0]["content"], "hello")
            reopened.close()


if __name__ == "__main__":
    unittest.main()
