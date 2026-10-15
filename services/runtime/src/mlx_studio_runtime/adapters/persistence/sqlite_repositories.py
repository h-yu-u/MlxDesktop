"""Composition of focused SQLite repositories; no business CRUD facade."""

from pathlib import Path

from mlx_studio_runtime.adapters.persistence.attachment_repository import (
    AttachmentRepository,
)
from mlx_studio_runtime.adapters.persistence.conversation_repository import (
    ConversationRepository,
)
from mlx_studio_runtime.adapters.persistence.image_repository import ImageRepository
from mlx_studio_runtime.adapters.persistence.job_repository import JobRepository
from mlx_studio_runtime.adapters.persistence.model_repository import ModelRepository
from mlx_studio_runtime.adapters.persistence.sqlite_database import SQLiteDatabase


class SQLiteRepositories:
    def __init__(self, path: Path) -> None:
        self.database = SQLiteDatabase(path)
        self.attachments = AttachmentRepository(self.database)
        self.models = ModelRepository(self.database)
        self.conversations = ConversationRepository(self.database, self.attachments)
        self.jobs = JobRepository(self.database)
        self.images = ImageRepository(self.database)

    @property
    def database_path(self) -> Path:
        return self.database.path

    @property
    def media_path(self) -> Path:
        return self.database.media_path

    def close(self) -> None:
        self.database.close()
