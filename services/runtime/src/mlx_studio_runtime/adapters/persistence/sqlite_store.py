"""SQLite metadata store with an explicit initial schema migration."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.database_path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.migrate()

    @property
    def media_path(self) -> Path:
        data_directory = self.database_path.parent
        app_directory = data_directory.parent if data_directory.name == "data" else data_directory
        return app_directory / "media"

    def migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version INTEGER PRIMARY KEY, applied_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
              key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS models (
              id TEXT PRIMARY KEY, manifest_json TEXT NOT NULL, state TEXT NOT NULL,
              created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversations (
              id TEXT PRIMARY KEY, title TEXT NOT NULL, model_id TEXT,
              parameters_json TEXT NOT NULL DEFAULT '{}', created_at INTEGER NOT NULL,
              updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
              id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
              role TEXT NOT NULL, content TEXT NOT NULL, model_snapshot_json TEXT,
              parameters_json TEXT NOT NULL DEFAULT '{}', created_at INTEGER NOT NULL,
              turn_id TEXT
            );
            CREATE INDEX IF NOT EXISTS messages_conversation_created
              ON messages(conversation_id, created_at);
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL,
              model_id TEXT, request_json TEXT NOT NULL, error_code TEXT,
              created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS artifacts (
              id TEXT PRIMARY KEY, job_id TEXT REFERENCES jobs(id), kind TEXT NOT NULL,
              relative_path TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attachments (
              id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, mime_type TEXT NOT NULL,
              size_bytes INTEGER NOT NULL, relative_path TEXT NOT NULL,
              original_name TEXT NOT NULL, created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS message_attachments (
              message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
              attachment_id TEXT NOT NULL REFERENCES attachments(id) ON DELETE RESTRICT,
              position INTEGER NOT NULL, PRIMARY KEY(message_id, attachment_id)
            );
            CREATE TABLE IF NOT EXISTS runtime_sessions (
              id TEXT PRIMARY KEY, protocol_version INTEGER NOT NULL,
              started_at INTEGER NOT NULL, ended_at INTEGER
            );
            INSERT OR IGNORE INTO schema_migrations(version, applied_at)
              VALUES (1, CAST(strftime('%s','now') AS INTEGER));
            """
        )
        message_columns = {
            row[1] for row in self.connection.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "turn_id" not in message_columns:
            self.connection.execute("ALTER TABLE messages ADD COLUMN turn_id TEXT")
        self.connection.commit()

    def save_attachment(self, item: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO attachments(id,sha256,mime_type,size_bytes,relative_path,"
            "original_name,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                item["id"],
                item["sha256"],
                item["mimeType"],
                item["sizeBytes"],
                item["relativePath"],
                item["originalName"],
                int(time.time()),
            ),
        )
        self.connection.commit()

    def get_attachments(self, attachment_ids: list[str]) -> list[dict[str, Any]] | None:
        if not attachment_ids:
            return []
        placeholders = ",".join("?" for _ in attachment_ids)
        rows = self.connection.execute(
            f"SELECT id,sha256,mime_type,size_bytes,relative_path,original_name FROM attachments "
            f"WHERE id IN ({placeholders})",
            attachment_ids,
        ).fetchall()
        by_id = {
            row[0]: {
                "id": row[0],
                "sha256": row[1],
                "mimeType": row[2],
                "sizeBytes": row[3],
                "relativePath": row[4],
                "originalName": row[5],
            }
            for row in rows
        }
        if len(by_id) != len(set(attachment_ids)):
            return None
        return [by_id[attachment_id] for attachment_id in attachment_ids]

    def list_models(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT manifest_json,state FROM models ORDER BY created_at"
        ).fetchall()
        return [{**json.loads(row[0]), "state": row[1]} for row in rows]

    def upsert_model(self, manifest: dict[str, Any], state: str = "available") -> None:
        now = int(time.time())
        self.connection.execute(
            "INSERT INTO models(id,manifest_json,state,created_at,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET manifest_json=excluded.manifest_json,"
            "state=excluded.state,updated_at=excluded.updated_at",
            (manifest["id"], json.dumps(manifest), state, now, now),
        )
        self.connection.commit()

    def remove_model(self, model_id: str) -> bool:
        cursor = self.connection.execute("DELETE FROM models WHERE id=?", (model_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    def list_conversations(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id,title,model_id,parameters_json,created_at,updated_at "
            "FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
        return [self._conversation(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT id,title,model_id,parameters_json,created_at,updated_at "
            "FROM conversations WHERE id=?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        conversation = self._conversation(row)
        messages = self.connection.execute(
            "SELECT id,role,content,model_snapshot_json,parameters_json,created_at,turn_id "
            "FROM messages WHERE conversation_id=? ORDER BY created_at, rowid",
            (conversation_id,),
        ).fetchall()
        conversation["messages"] = [
            {
                "id": item[0],
                "role": item[1],
                "content": item[2],
                "modelSnapshot": json.loads(item[3]) if item[3] else None,
                "parameters": json.loads(item[4]),
                "createdAt": item[5],
                "attachments": self.get_attachments_for_message(item[0]),
                "turnId": item[6] or item[0],
            }
            for item in messages
        ]
        conversation["messages"] = _order_messages_by_turn(conversation["messages"])
        return conversation

    def save_conversation(self, item: dict[str, Any]) -> None:
        now = int(time.time())
        self.connection.execute(
            "INSERT INTO conversations(id,title,model_id,parameters_json,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                item["id"],
                item["title"],
                item.get("modelId"),
                json.dumps(item.get("parameters", {})),
                now,
                now,
            ),
        )
        self.connection.commit()

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        cursor = self.connection.execute(
            "UPDATE conversations SET title=?,updated_at=? WHERE id=?",
            (title, int(time.time()), conversation_id),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def delete_conversation(self, conversation_id: str) -> bool:
        cursor = self.connection.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    def delete_last_assistant_message(self, conversation_id: str) -> bool:
        row = self.connection.execute(
            "SELECT id FROM messages WHERE conversation_id=? AND role='assistant' "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return False
        self.connection.execute("DELETE FROM messages WHERE id=?", (row[0],))
        self.connection.commit()
        return True

    def save_message(self, item: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO messages(id,conversation_id,role,content,model_snapshot_json,"
            "parameters_json,created_at,turn_id) VALUES(?,?,?,?,?,?,?,?)",
            (
                item["id"],
                item["conversationId"],
                item["role"],
                item["content"],
                json.dumps(item["modelSnapshot"]) if item.get("modelSnapshot") else None,
                json.dumps(item.get("parameters", {})),
                int(time.time()),
                item.get("turnId"),
            ),
        )
        for position, attachment_id in enumerate(item.get("attachmentIds", [])):
            self.connection.execute(
                "INSERT INTO message_attachments(message_id,attachment_id,position) VALUES(?,?,?)",
                (item["id"], attachment_id, position),
            )
        self.connection.execute(
            "UPDATE conversations SET updated_at=? WHERE id=?",
            (int(time.time()), item["conversationId"]),
        )
        self.connection.commit()

    def get_attachments_for_message(self, message_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT a.id,a.sha256,a.mime_type,a.size_bytes,a.original_name "
            "FROM message_attachments ma JOIN attachments a ON a.id=ma.attachment_id "
            "WHERE ma.message_id=? ORDER BY ma.position",
            (message_id,),
        ).fetchall()
        return [
            {"id": r[0], "sha256": r[1], "mimeType": r[2], "sizeBytes": r[3], "originalName": r[4]}
            for r in rows
        ]

    def save_job(self, item: dict[str, Any]) -> None:
        now = int(time.time())
        self.connection.execute(
            "INSERT INTO jobs(id,kind,state,model_id,request_json,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                item["id"],
                item["kind"],
                item["state"],
                item.get("modelId"),
                json.dumps(item.get("request", {})),
                now,
                now,
            ),
        )
        self.connection.commit()

    def update_job(self, job_id: str, state: str, error_code: str | None = None) -> None:
        self.connection.execute(
            "UPDATE jobs SET state=?,error_code=?,updated_at=? WHERE id=?",
            (state, error_code, int(time.time()), job_id),
        )
        self.connection.commit()

    def list_jobs(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id,kind,state,model_id,error_code,created_at,updated_at "
            "FROM jobs ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
        return [
            {
                "id": row[0],
                "kind": row[1],
                "state": row[2],
                "modelId": row[3],
                "errorCode": row[4],
                "createdAt": row[5],
                "updatedAt": row[6],
            }
            for row in rows
        ]

    @staticmethod
    def _conversation(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row[0],
            "title": row[1],
            "modelId": row[2],
            "parameters": json.loads(row[3]),
            "createdAt": row[4],
            "updatedAt": row[5],
        }

    def close(self) -> None:
        self.connection.close()


def _order_messages_by_turn(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: dict[str, list[dict[str, Any]]] = {}
    turn_order: list[str] = []
    for message in messages:
        turn_id = str(message.get("turnId") or message["id"])
        if turn_id not in turns:
            turns[turn_id] = []
            turn_order.append(turn_id)
        turns[turn_id].append(message)
    ordered: list[dict[str, Any]] = []
    for turn_id in turn_order:
        messages_in_turn = turns[turn_id]
        ordered.extend(sorted(messages_in_turn, key=lambda item: item["role"] != "user"))
    return ordered
