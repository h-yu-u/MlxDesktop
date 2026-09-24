"""Facade over focused SQLite repositories."""

from pathlib import Path
from typing import Any

from mlx_studio_runtime.adapters.persistence.attachment_repository import (
    AttachmentRepository,
)
from mlx_studio_runtime.adapters.persistence.conversation_repository import (
    ConversationRepository,
)
from mlx_studio_runtime.adapters.persistence.job_repository import JobRepository
from mlx_studio_runtime.adapters.persistence.model_repository import ModelRepository
from mlx_studio_runtime.adapters.persistence.sqlite_database import SQLiteDatabase


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.database = SQLiteDatabase(path)
        self.attachments = AttachmentRepository(self.database)
        self.models = ModelRepository(self.database)
        self.conversations = ConversationRepository(self.database, self.attachments)
        self.jobs = JobRepository(self.database)

    @property
    def database_path(self) -> Path:
        return self.database.path

    @property
    def media_path(self) -> Path:
        return self.database.media_path

    def save_attachment(self, item: dict[str, Any]) -> None:
        self.attachments.save(item)

    def get_attachments(self, attachment_ids: list[str]) -> list[dict[str, Any]] | None:
        return self.attachments.get_many(attachment_ids)

    def get_attachments_for_message(self, message_id: str) -> list[dict[str, Any]]:
        return self.attachments.for_message(message_id)

    def list_models(self) -> list[dict[str, Any]]:
        return self.models.list()

    def upsert_model(self, manifest: dict[str, Any], state: str = "available") -> None:
        self.models.upsert(manifest, state)

    def update_model_state(self, model_id: str, state: str) -> None:
        self.models.update_state(model_id, state)

    def remove_model(self, model_id: str) -> bool:
        return self.models.remove(model_id)

    def list_conversations(self) -> list[dict[str, Any]]:
        return self.conversations.list()

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        return self.conversations.get(conversation_id)

    def save_conversation(self, item: dict[str, Any]) -> None:
        self.conversations.save(item)

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        return self.conversations.rename(conversation_id, title)

    def delete_conversation(self, conversation_id: str) -> bool:
        return self.conversations.delete(conversation_id)

    def last_assistant_message_id(self, conversation_id: str) -> str | None:
        return self.conversations.last_assistant_message_id(conversation_id)

    def delete_last_assistant_message(self, conversation_id: str) -> bool:
        return self.conversations.delete_last_assistant_message(conversation_id)

    def save_message(
        self,
        item: dict[str, Any],
        replace_message_id: str | None = None,
    ) -> None:
        self.conversations.save_message(item, replace_message_id)

    def save_job(self, item: dict[str, Any]) -> None:
        self.jobs.save(item)

    def update_job(self, job_id: str, state: str, error_code: str | None = None) -> None:
        self.jobs.update(job_id, state, error_code)

    def recover_interrupted_jobs(self, error_code: str) -> int:
        return self.jobs.recover_interrupted(error_code)

    def list_jobs(self) -> list[dict[str, Any]]:
        return self.jobs.list()

    def close(self) -> None:
        self.database.close()
