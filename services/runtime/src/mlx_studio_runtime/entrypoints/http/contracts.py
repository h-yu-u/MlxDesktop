"""Explicit query contracts; transport DTOs stay outside the domain."""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReadModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class ModelView(ReadModel):
    id: str
    displayName: str
    source: str
    engine: str
    task: str
    state: str = "available"
    localPath: str
    inputModalities: list[str]
    outputModalities: list[str]
    contextLength: int | None = None
    capabilities: dict[str, bool]
    installationId: str | None = None
    managedInstallation: bool = False
    artifactIdentity: str | None = None


class AttachmentView(ReadModel):
    id: str
    mimeType: str
    originalName: str


class MessageView(ReadModel):
    id: str
    role: str
    content: str
    turnId: str
    parameters: dict[str, Any]
    attachments: list[AttachmentView]


class ConversationView(ReadModel):
    pinned: bool = False
    id: str
    title: str
    modelId: str | None = None
    messages: list[MessageView] = Field(default_factory=list)


class ChatSubmission(ReadModel):
    jobId: str
    state: str


class RuntimeInfo(ReadModel):
    version: str
    protocol_version: int
    pid: int
    platform: str
    state: str
    active_model_id: str | None
    event_sequence: int
    instance_id: str


class RuntimeMetrics(ReadModel):
    uptime_seconds: float
    process_max_rss_bytes: int
    disk_free_bytes: int
    worker_restarts: int
    active_jobs: int
    system_memory_total_bytes: int | None
    system_memory_used_bytes: int | None
    system_memory_available_bytes: int | None
    system_memory_used_percent: float | None
    worker_memory_bytes: int | None


class JobView(ReadModel):
    id: str
    kind: str
    state: str
    modelId: str | None
    errorCode: str | None


class JobSnapshot(JobView):
    text: str
    event_sequence: int
    instance_id: str


class ErrorInfo(BaseModel):
    code: str
    message: str
    retryable: bool
    details: dict[str, Any]
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorInfo


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", max_length=160)
    model_id: str | None = None


class ConversationPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=160)
    pinned: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.title is None and self.pinned is None:
            raise ValueError("Provide a title or pinned state")
        return self


class ChatMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=200_000)
    model_id: str = Field(min_length=1, max_length=200)
    max_tokens: int = Field(default=4096, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0, le=2)
    attachment_ids: list[str] = Field(default_factory=list, max_length=4)
    client_request_id: str | None = Field(default=None, min_length=1, max_length=100)


class ModelPathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class ModelPullRequest(BaseModel):
    repo_id: str = Field(min_length=3, max_length=200)
    revision: str | None = Field(default=None, max_length=200)
