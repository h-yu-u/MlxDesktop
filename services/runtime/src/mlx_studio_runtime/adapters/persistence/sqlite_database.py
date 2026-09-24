"""SQLite connection, schema migration, and transaction boundary."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class SQLiteDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    @property
    def media_path(self) -> Path:
        data_directory = self.path.parent
        app_directory = data_directory.parent if data_directory.name == "data" else data_directory
        return app_directory / "media"

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            yield self.connection
        except BaseException:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
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
        columns = {
            row[1]
            for row in self.connection.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "turn_id" not in columns:
            self.connection.execute("ALTER TABLE messages ADD COLUMN turn_id TEXT")
        self.connection.commit()
