"""Product DTOs mirrored by the private host protocol; OpenAPI generates UI types."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CodingProjectRequest(StrictRequest):
    path: str = Field(min_length=1, max_length=4096)


class CodingProjectPatch(StrictRequest):
    commands: list[str] = Field(max_length=8)


class CodingSessionRequest(StrictRequest):
    title: str = Field(default="新开发会话", min_length=1, max_length=160)


class CodingSessionPatch(StrictRequest):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    pinned: bool | None = None
    archived: bool | None = None


class CodingRunRequest(StrictRequest):
    submissionId: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=32000)
    modelId: str
    mode: Literal["analyze", "develop", "review"] = "develop"
    queue: bool = False


class CodingSteerRequest(StrictRequest):
    text: str = Field(min_length=1, max_length=16000)


class CodingApprovalRequest(StrictRequest):
    allowed: bool


class CodingProjectView(BaseModel):
    id: str
    path: str
    name: str
    git: bool
    branch: str
    dirty: str
    instructions: str
    commands: list[str]


class CodingSessionView(BaseModel):
    id: str
    projectId: str
    title: str
    pinned: bool
    archived: bool
    piPath: str | None


class CodingRunView(BaseModel):
    id: str
    sessionId: str
    submissionId: str
    text: str
    modelId: str
    mode: Literal["analyze", "develop", "review"]
    status: Literal[
        "queued",
        "starting",
        "running",
        "awaiting_approval",
        "cancelling",
        "completed",
        "failed",
        "cancelled",
        "interrupted",
    ]
    phase: str
    verification: Literal["not_run", "running", "passed", "failed", "partial"]
    error: str | None
    createdAt: str
    baseline: str
    fingerprint: str | None
    maxRepairRounds: int


class CodingApprovalView(BaseModel):
    id: str
    runId: str
    sessionId: str
    toolCallId: str
    action: Literal["command", "file_write"]
    parameters: dict[str, object]
    command: str
    cwd: str
    policyVersion: Literal[1]
    expiresAt: int
    status: Literal["pending", "allowed", "denied"]


class CodingVerificationView(BaseModel):
    purpose: Literal["command", "verification"] = "command"
    id: str
    runId: str
    sessionId: str
    command: str
    exitCode: int | None
    output: str
    truncated: bool
    fingerprint: str
    stale: bool


class CodingChangeView(BaseModel):
    contentLoaded: bool = True
    id: str
    runId: str
    sessionId: str
    path: str
    before: str | None
    after: str
    restored: bool
    state: Literal["pending", "written"]


class CodingEventView(BaseModel):
    seq: int
    sessionId: str
    runId: str | None
    type: str
    text: str
    data: object


class CodingSnapshot(BaseModel):
    session: CodingSessionView
    project: CodingProjectView
    runs: list[CodingRunView]
    approvals: list[CodingApprovalView]
    verifications: list[CodingVerificationView]
    events: list[CodingEventView]
    watermark: int
    activeRun: CodingRunView | None


class CodingChanges(BaseModel):
    managed: list[CodingChangeView]
    workspace: str
    diff: str
    scope: str


class CodingCapability(BaseModel):
    id: str
    status: Literal["verified", "unverified"]
    verifiedAt: str | None
    engineVersion: str
    parserVersion: str
    modelFingerprint: str
    detail: str


class CodingFileList(BaseModel):
    files: list[str]


class CodingFileView(BaseModel):
    content: str
    sha256: str


class CodingSettings(StrictRequest):
    id: Literal["coding"] = "coding"
    defaultModelId: str = Field(default="", max_length=128)
    contextBudget: int = Field(default=32768, ge=4096, le=32768)
    maxRepairRounds: int = Field(default=2, ge=0, le=2)
