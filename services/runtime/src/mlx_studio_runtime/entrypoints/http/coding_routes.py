"""Thin authenticated Coding gateway; business state stays in the Node Host."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import StreamingResponse

from mlx_studio_runtime.composition_root import RuntimeApplication
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.entrypoints.http.coding_contracts import (
    CodingApprovalRequest,
    CodingCapability,
    CodingChanges,
    CodingChangeView,
    CodingFileList,
    CodingFileView,
    CodingProjectPatch,
    CodingProjectRequest,
    CodingProjectView,
    CodingRunRequest,
    CodingRunView,
    CodingSessionPatch,
    CodingSessionRequest,
    CodingSessionView,
    CodingSettings,
    CodingSnapshot,
    CodingSteerRequest,
)


def register_coding_routes(
    app: FastAPI, service: RuntimeApplication, authenticate: Callable[..., Awaitable[None]]
) -> None:
    from fastapi import APIRouter

    router = APIRouter(prefix="/internal/v1/coding", dependencies=[Depends(authenticate)])
    call = service.coding.call

    async def model_call(
        method: str, params: dict[str, object], request: Request, model_id: str
    ) -> Any:
        model = service.catalog.models.get(model_id)
        if model is None or "text" not in model.output_modalities:
            raise RuntimeFault(RuntimeErrorInfo("MODEL_NOT_FOUND", "请选择本地文本模型"))
        return await service.coding.model_call(
            method,
            params,
            str(request.base_url),
            model.id,
            min(model.context_length or 32768, 32768),
            service.coding_identity(model),
        )

    @router.get("/settings", response_model=CodingSettings)
    async def settings():
        return await call("settings.get", {})

    @router.patch("/settings", response_model=CodingSettings)
    async def update_settings(body: CodingSettings):
        return await call("settings.update", body.model_dump())

    @router.get("/projects", response_model=list[CodingProjectView])
    async def projects():
        return await call("projects.list", {})

    @router.post("/projects", response_model=CodingProjectView)
    async def register(body: CodingProjectRequest):
        return await call("projects.register", body.model_dump())

    @router.get("/projects/{project_id}", response_model=CodingProjectView)
    async def project(project_id: str):
        return await call("projects.get", {"id": project_id})

    @router.patch("/projects/{project_id}", response_model=CodingProjectView)
    async def update_project(project_id: str, body: CodingProjectPatch):
        return await call("projects.update", {"id": project_id, **body.model_dump()})

    @router.delete("/projects/{project_id}")
    async def remove_project(project_id: str):
        return await call("projects.remove", {"id": project_id})

    @router.get("/projects/{project_id}/sessions", response_model=list[CodingSessionView])
    async def sessions(project_id: str):
        return await call("sessions.list", {"projectId": project_id})

    @router.post("/projects/{project_id}/sessions", response_model=CodingSessionView)
    async def create_session(project_id: str, body: CodingSessionRequest):
        return await call("sessions.create", {"projectId": project_id, **body.model_dump()})

    @router.get("/sessions/{session_id}", response_model=CodingSessionView)
    async def session(session_id: str):
        return await call("sessions.get", {"id": session_id})

    @router.patch("/sessions/{session_id}", response_model=CodingSessionView)
    async def update_session(session_id: str, body: CodingSessionPatch):
        return await call(
            "sessions.update", {"id": session_id, **body.model_dump(exclude_none=True)}
        )

    @router.delete("/sessions/{session_id}")
    async def remove_session(session_id: str):
        return await call("sessions.remove", {"id": session_id})

    @router.get("/sessions/{session_id}/snapshot", response_model=CodingSnapshot)
    async def snapshot(session_id: str):
        return await call("sessions.snapshot", {"id": session_id})

    @router.get("/sessions/{session_id}/changes", response_model=CodingChanges)
    async def changes(session_id: str, diff: bool = False):
        return await call("sessions.changes", {"id": session_id, "diff": diff})

    @router.get("/sessions/{session_id}/files", response_model=CodingFileList)
    async def files(session_id: str):
        return await call("sessions.files", {"id": session_id})

    @router.get("/sessions/{session_id}/file", response_model=CodingFileView)
    async def read_file(session_id: str, path: str = Query(max_length=4096)):
        return await call("sessions.read", {"id": session_id, "path": path})

    @router.get("/changes/{change_id}", response_model=CodingChangeView)
    async def get_change(change_id: str):
        return await call("changes.get", {"id": change_id})

    @router.post("/changes/{change_id}/restore")
    async def restore(change_id: str):
        return await call("changes.restore", {"id": change_id})

    @router.post("/sessions/{session_id}/runs", response_model=CodingRunView)
    async def submit(session_id: str, body: CodingRunRequest, request: Request):
        return await model_call(
            "runs.submit",
            {"sessionId": session_id, **body.model_dump(exclude={"modelId"})},
            request,
            body.modelId,
        )

    @router.post("/sessions/{session_id}/verify", response_model=CodingRunView)
    async def verify_session(session_id: str, body: CodingRunRequest, request: Request):
        return await model_call(
            "sessions.verify",
            {"sessionId": session_id, "submissionId": body.submissionId},
            request,
            body.modelId,
        )

    @router.post("/runs/{run_id}/steer")
    async def steer(run_id: str, body: CodingSteerRequest):
        return await call("runs.steer", {"id": run_id, **body.model_dump()})

    @router.post("/cancel-active")
    async def cancel_active():
        return await call("runs.cancel-active", {})

    @router.post("/runs/{run_id}/cancel", response_model=CodingRunView)
    async def cancel(run_id: str):
        return await call("runs.cancel", {"id": run_id})

    @router.post("/approvals/{approval_id}/resolve")
    async def resolve(approval_id: str, body: CodingApprovalRequest):
        return await call("approvals.resolve", {"id": approval_id, **body.model_dump()})

    @router.get("/capabilities", response_model=list[CodingCapability])
    async def capabilities():
        return await call("capabilities.list", {})

    @router.post("/capabilities/{model_id}/verify", response_model=CodingCapability)
    async def verify_model(model_id: str, request: Request):
        return await model_call("capabilities.verify", {}, request, model_id)

    @router.get("/events")
    async def events(request: Request, after_seq: int = Query(default=0, ge=0)):
        async def stream():
            sequence = after_seq
            while not await request.is_disconnected():
                batch = await call("events.list", {"after": sequence})
                for event in batch["events"]:
                    sequence = event["seq"]
                    yield f"id: {sequence}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream")

    app.include_router(router)
