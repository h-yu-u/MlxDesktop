import sqlite3
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

    def test_message_write_rolls_back_when_attachment_relation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "app.db")
            store.save_conversation({"id": "conversation-1", "title": "Test"})
            with self.assertRaises(sqlite3.IntegrityError):
                store.save_message(
                    {
                        "id": "message-1",
                        "conversationId": "conversation-1",
                        "role": "user",
                        "content": "hello",
                        "attachmentIds": ["missing-attachment"],
                    }
                )
            store.save_message(
                {
                    "id": "message-2",
                    "conversationId": "conversation-1",
                    "role": "user",
                    "content": "after rollback",
                }
            )
            conversation = store.get_conversation("conversation-1")
            self.assertEqual(
                [message["id"] for message in conversation["messages"]],
                ["message-2"],
            )
            store.close()

    def test_attachment_file_is_removed_when_registration_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "data" / "app.db")
            store.save_attachment(
                {
                    "id": "duplicate",
                    "sha256": "first",
                    "mimeType": "image/png",
                    "sizeBytes": 8,
                    "relativePath": "attachments/first",
                    "originalName": "first.png",
                }
            )
            orphan = store.media_path / "attachments" / "orphan"
            orphan.parent.mkdir(parents=True, exist_ok=True)
            orphan.write_bytes(b"orphan")
            with self.assertRaises(sqlite3.IntegrityError):
                store.save_attachment(
                    {
                        "id": "duplicate",
                        "sha256": "second",
                        "mimeType": "image/png",
                        "sizeBytes": 6,
                        "relativePath": "attachments/orphan",
                        "originalName": "orphan.png",
                    }
                )
            self.assertFalse(orphan.exists())
            store.close()

    def test_recover_interrupted_jobs_marks_them_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "app.db")
            store.save_job({"id": "job-1", "kind": "chat", "state": "running"})
            self.assertEqual(store.recover_interrupted_jobs("RUNTIME_RESTARTED"), 1)
            job = store.list_jobs()[0]
            self.assertEqual(job["state"], "failed")
            self.assertEqual(job["errorCode"], "RUNTIME_RESTARTED")
            store.close()

    def test_assistant_replacement_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "app.db")
            store.save_conversation({"id": "conversation-1", "title": "Test"})
            store.save_message(
                {
                    "id": "user-1",
                    "turnId": "turn-1",
                    "conversationId": "conversation-1",
                    "role": "user",
                    "content": "question",
                }
            )
            store.save_message(
                {
                    "id": "assistant-old",
                    "turnId": "turn-1",
                    "conversationId": "conversation-1",
                    "role": "assistant",
                    "content": "old",
                }
            )
            store.save_message(
                {
                    "id": "assistant-new",
                    "turnId": "turn-1",
                    "conversationId": "conversation-1",
                    "role": "assistant",
                    "content": "new",
                },
                replace_message_id="assistant-old",
            )
            messages = store.get_conversation("conversation-1")["messages"]
            self.assertEqual([item["content"] for item in messages], ["question", "new"])
            store.close()


if __name__ == "__main__":
    unittest.main()
