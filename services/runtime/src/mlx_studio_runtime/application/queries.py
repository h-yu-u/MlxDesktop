"""Read use cases keep repository access and missing-resource rules out of routes."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mlx_studio_runtime.application.chat_context_ports import ChatContexts
from mlx_studio_runtime.application.job_lifecycle import JobLifecycle
from mlx_studio_runtime.application.ports import (
    ConversationRepository,
    ImageRepository,
    JobRepository,
)
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault


class Queries:
    def __init__(
        self,
        conversations: ConversationRepository,
        jobs: JobRepository,
        images: ImageRepository,
        lifecycle: JobLifecycle,
        image_path: Callable[[str], Path],
        contexts: ChatContexts | None = None,
    ) -> None:
        self.conversations = conversations
        self.jobs = jobs
        self.images = images
        self.lifecycle = lifecycle
        self.image_path = image_path
        self.contexts = contexts

    def conversation(self, conversation_id: str) -> dict[str, Any]:
        item = self.conversations.get(conversation_id)
        if item is None:
            raise RuntimeFault(RuntimeErrorInfo("CONVERSATION_NOT_FOUND", "找不到此会话"))
        return item

    def rename(self, conversation_id: str, title: str) -> dict[str, Any]:
        if not self.conversations.rename(conversation_id, title):
            raise RuntimeFault(RuntimeErrorInfo("CONVERSATION_NOT_FOUND", "找不到此会话"))
        return self.conversation(conversation_id)

    def update_conversation(
        self,
        conversation_id: str,
        title: str | None,
        pinned: bool | None,
        web_search_enabled: bool | None = None,
    ) -> dict[str, Any]:
        if not self.conversations.update_metadata(
            conversation_id, title, pinned, web_search_enabled
        ):
            raise RuntimeFault(RuntimeErrorInfo("CONVERSATION_NOT_FOUND", "找不到此会话"))
        return self.conversation(conversation_id)

    def delete(self, conversation_id: str) -> dict[str, bool]:
        for job in self.jobs.list():
            if job["state"] not in {"succeeded", "failed", "cancelled"}:
                detail = self.jobs.get(job["id"])
                if detail and detail["request"].get("conversationId") == conversation_id:
                    raise RuntimeFault(
                        RuntimeErrorInfo("CONVERSATION_IN_USE", "会话仍有任务运行", True)
                    )
        if not self.conversations.delete(conversation_id):
            raise RuntimeFault(RuntimeErrorInfo("CONVERSATION_NOT_FOUND", "找不到此会话"))
        return {"deleted": True}

    def job(self, job_id: str) -> dict[str, Any]:
        item = self.jobs.get(job_id)
        if item is None:
            raise RuntimeFault(RuntimeErrorInfo("JOB_NOT_FOUND", "找不到此任务"))
        sources: list[dict[str, Any]] = []
        request = item["request"]
        if self.contexts and item["kind"] == "chat":
            try:
                sources = self.contexts.load(job_id, request["conversationId"], request["turnId"])[
                    "sources"
                ]
            except RuntimeFault:
                pass  # Legacy/unfinished jobs have no context yet.
        result_text = item.pop("resultText", "")
        return dict(
            item,
            text=self.lifecycle.output_text(job_id) or result_text,
            textRevision=self.lifecycle.text_revision(job_id),
            sources=sources,
        )

    def list_conversations(self) -> list[dict[str, Any]]:
        return self.conversations.list()

    def list_jobs(self) -> list[dict[str, Any]]:
        return self.jobs.list()

    def history(self, limit: int, offset: int) -> list[dict[str, Any]]:
        return self.images.list_artifacts(limit, offset)

    def image_artifact(self, artifact_id: str) -> dict[str, Any]:
        item = self.images.get(artifact_id)
        if item is None:
            raise RuntimeFault(RuntimeErrorInfo("IMAGE_ARTIFACT_NOT_FOUND", "找不到此作品"))
        return item

    def image_content(self, artifact_id: str) -> Path:
        return self.image_path(str(self.image_artifact(artifact_id)["relative_path"]))
