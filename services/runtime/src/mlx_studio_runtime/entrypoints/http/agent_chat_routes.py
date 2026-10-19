"""Explicit Agent Chat sessions have their own Node metadata and Pi transcripts."""

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field

from mlx_studio_runtime.application.extension_gateway import public_projection
from mlx_studio_runtime.composition_root import RuntimeApplication
from mlx_studio_runtime.entrypoints.http.coding_contracts import (
    CodingApprovalView,
    CodingEventView,
    CodingRunView,
)
from mlx_studio_runtime.entrypoints.http.extension_models import ExtensionSelection


class AgentSessionView(BaseModel):
    id: str
    title: str
    piPath: str | None


class AgentSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="工具助手", min_length=1, max_length=160)


class AgentChatRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    submissionId: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=32000)
    modelId: str
    mode: Literal["develop"] = "develop"
    selection: ExtensionSelection | None = None


class AgentChatSnapshot(BaseModel):
    session: AgentSessionView
    runs: list[CodingRunView]
    approvals: list[CodingApprovalView]
    events: list[CodingEventView]


class AgentApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed: bool


def register_agent_chat_routes(
    app: FastAPI, service: RuntimeApplication, authenticate: Callable[..., Awaitable[None]]
) -> None:
    router = APIRouter(prefix="/internal/v1/agent-chat", dependencies=[Depends(authenticate)])
    call = service.coding.call

    @router.get("/sessions", response_model=list[AgentSessionView])
    async def sessions() -> Any:
        return await call("agent.sessions.list", {})

    @router.post("/sessions", response_model=AgentSessionView)
    async def create(body: AgentSessionCreate) -> Any:
        return await call("agent.sessions.create", body.model_dump())

    @router.get("/sessions/{identifier}", response_model=AgentChatSnapshot)
    async def snapshot(identifier: str) -> Any:
        return public_projection(await call("agent.sessions.snapshot", {"id": identifier}))

    @router.post("/sessions/{identifier}/runs", response_model=CodingRunView)
    async def submit(identifier: str, body: AgentChatRunRequest, request: Request) -> Any:
        params = {
            "sessionId": identifier,
            **body.model_dump(exclude={"modelId"}, exclude_none=True),
        }
        return public_projection(
            await service.coding_submissions.submit(
                params, str(request.base_url), body.modelId, agent=True
            )
        )

    @router.post("/runs/{identifier}/cancel", response_model=CodingRunView)
    async def cancel(identifier: str) -> Any:
        await service.capability_grants.cancel_id(identifier)
        return public_projection(await call("agent.runs.cancel", {"id": identifier}))

    @router.post("/approvals/{identifier}/resolve")
    async def resolve(identifier: str, body: AgentApprovalRequest) -> Any:
        return await call("agent.approvals.resolve", {"id": identifier, "allowed": body.allowed})

    app.include_router(router)
