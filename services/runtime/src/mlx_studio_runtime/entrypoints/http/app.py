"""Loopback-only FastAPI Supervisor API with ephemeral bearer authentication."""

import asyncio
import hashlib
import hmac
import io
import json
import os
import platform
import resource
import shutil
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from mlx_studio_runtime import PROTOCOL_VERSION
from mlx_studio_runtime.adapters.persistence.sqlite_store import SQLiteStore
from mlx_studio_runtime.application.runtime_service import RuntimeService
from mlx_studio_runtime.domain.errors import RuntimeFault, error_payload

RUNTIME_SOURCE = Path(__file__).parents[3]


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", max_length=160)
    model_id: str | None = None


class ConversationPatch(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class ChatMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=200_000)
    model_id: str = Field(min_length=1, max_length=200)
    max_tokens: int = Field(default=512, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0, le=2)
    attachment_ids: list[str] = Field(default_factory=list, max_length=4)


class ModelPathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class ModelPullRequest(BaseModel):
    repo_id: str = Field(min_length=3, max_length=200)
    revision: str | None = Field(default=None, max_length=200)


class ImageJobRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)
    model_id: str = Field(min_length=1, max_length=200)
    seed: int | None = None
    width: int = Field(default=512, ge=64, le=2048)
    height: int = Field(default=512, ge=64, le=2048)
    steps: int = Field(default=20, ge=1, le=100)


def _data_path() -> Path:
    configured = os.getenv("MLX_STUDIO_DATA_DIR")
    if configured:
        return Path(configured).expanduser() / "app.db"
    return Path.home() / "Library" / "Application Support" / "MLX Studio" / "data" / "app.db"


def create_app(
    session_token: str | None = None,
    database_path: Path | None = None,
    external_api_enabled: bool | None = None,
) -> FastAPI:
    token = (
        session_token if session_token is not None else os.getenv("MLX_STUDIO_SESSION_TOKEN", "")
    )
    external_enabled = (
        external_api_enabled
        if external_api_enabled is not None
        else os.getenv("MLX_STUDIO_EXTERNAL_API_ENABLED", "false").lower() == "true"
    )
    store = SQLiteStore(database_path or _data_path())
    service = RuntimeService(store, RUNTIME_SOURCE)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await service.close()

    app = FastAPI(
        title="MLX Studio Runtime",
        version="0.1.0",
        openapi_url="/internal/v1/openapi.json",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.service = service
    app.state.started_at = time.monotonic()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "tauri://localhost",
            "http://tauri.localhost",
            "http://127.0.0.1:1420",
            "http://localhost:1420",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    async def authenticate(authorization: str | None = Header(default=None)) -> None:
        if not token:
            raise HTTPException(status_code=503, detail="RUNTIME_SESSION_TOKEN_MISSING")
        expected = f"Bearer {token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="UNAUTHORIZED")

    @app.exception_handler(RuntimeFault)
    async def runtime_fault_handler(request: Request, error: RuntimeFault):
        return JSONResponse(
            status_code=_status_for_code(error.info.code),
            content=error_payload(error, request.state.request_id),
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, error: HTTPException):
        code = error.detail if isinstance(error.detail, str) else "REQUEST_REJECTED"
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": code,
                    "message": "请求未通过 Runtime 校验",
                    "retryable": False,
                    "details": {},
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, _error: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "请求参数无效",
                    "retryable": False,
                    "details": {},
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.get("/internal/v1/runtime/health", dependencies=[Depends(authenticate)])
    async def health() -> dict[str, object]:
        return {"status": "ok", "state": service.state.value, "protocol_version": PROTOCOL_VERSION}

    @app.get("/internal/v1/runtime/info", dependencies=[Depends(authenticate)])
    async def runtime_info() -> dict[str, object]:
        return {
            "version": app.version,
            "protocol_version": PROTOCOL_VERSION,
            "pid": os.getpid(),
            "platform": platform.platform(),
            "state": service.state.value,
            "active_model_id": service.active_model_id,
            "event_sequence": service.events.sequence,
        }

    @app.get("/internal/v1/runtime/metrics", dependencies=[Depends(authenticate)])
    async def metrics() -> dict[str, object]:
        return {
            "uptime_seconds": round(time.monotonic() - app.state.started_at, 3),
            "worker_restarts": service.worker_restarts,
            "active_jobs": sum(
                job.state.value in {"preparing", "running", "cancelling"}
                for job in service.jobs.values()
            ),
            "process_max_rss_bytes": int(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                * (1 if platform.system() == "Darwin" else 1024)
            ),
            "disk_free_bytes": _disk_free(_data_path().parent),
        }

    @app.get("/internal/v1/runtime/diagnostics", dependencies=[Depends(authenticate)])
    async def diagnostics() -> dict[str, object]:
        jobs = service.store.list_jobs()
        return {
            "runtime_state": service.state.value,
            "protocol_version": PROTOCOL_VERSION,
            "registered_models": len(service.models),
            "jobs_by_state": _counts(job["state"] for job in jobs),
        }

    @app.get("/internal/v1/runtime/diagnostics/bundle", dependencies=[Depends(authenticate)])
    async def diagnostic_bundle():
        jobs = service.store.list_jobs()
        report = {
            "runtime_version": app.version,
            "protocol_version": PROTOCOL_VERSION,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "uptime_seconds": round(time.monotonic() - app.state.started_at, 2),
            "runtime_state": service.state.value,
            "registered_models_by_engine": _counts(
                model.engine for model in service.models.values()
            ),
            "jobs_by_state": _counts(job["state"] for job in jobs),
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("diagnostics.json", json.dumps(report, ensure_ascii=False, indent=2))
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="mlx-studio-diagnostics.zip"'},
        )

    @app.post("/internal/v1/runtime/restart-worker", dependencies=[Depends(authenticate)])
    async def restart_worker() -> dict[str, str]:
        return await service.restart_worker()

    @app.get("/internal/v1/models", dependencies=[Depends(authenticate)])
    async def list_models() -> list[dict[str, Any]]:
        return service.list_models()

    @app.get("/internal/v1/models/{model_id}", dependencies=[Depends(authenticate)])
    async def get_model(model_id: str) -> dict[str, Any]:
        model = next((model for model in service.list_models() if model["id"] == model_id), None)
        if model is None:
            raise RuntimeFault(_not_found("MODEL_NOT_FOUND", "找不到此模型"))
        return model

    @app.post("/internal/v1/models/scan", dependencies=[Depends(authenticate)])
    async def scan_model(body: ModelPathRequest) -> dict[str, Any]:
        return await service.scan_model(Path(body.path).expanduser().resolve())

    @app.post("/internal/v1/models/import", dependencies=[Depends(authenticate)])
    async def import_model(body: ModelPathRequest) -> dict[str, Any]:
        return await service.scan_model(Path(body.path).expanduser().resolve())

    @app.post("/internal/v1/models/pull", dependencies=[Depends(authenticate)])
    async def pull_model(body: ModelPullRequest) -> dict[str, str]:
        return await _pull_model(body, service)

    @app.post("/internal/v1/attachments", dependencies=[Depends(authenticate)])
    async def upload_attachment(request: Request, filename: str = "image") -> dict[str, Any]:
        return await _save_attachment(request, filename, store, database_path or _data_path())

    @app.get("/internal/v1/attachments/{attachment_id}", dependencies=[Depends(authenticate)])
    async def read_attachment(attachment_id: str):
        items = store.get_attachments([attachment_id])
        if items is None:
            raise RuntimeFault(_not_found("ATTACHMENT_NOT_FOUND", "找不到此附件"))
        item = items[0]
        path = (store_path_root(database_path or _data_path()) / item["relativePath"]).resolve()
        if not path.is_file():
            raise RuntimeFault(_not_found("ATTACHMENT_NOT_FOUND", "附件文件已不存在"))
        return FileResponse(path, media_type=item["mimeType"], filename=item["originalName"])

    @app.post("/internal/v1/models/{model_id}/load", dependencies=[Depends(authenticate)])
    async def load_model(model_id: str) -> dict[str, str]:
        return await service.load_model(model_id)

    @app.post("/internal/v1/models/{model_id}/unload", dependencies=[Depends(authenticate)])
    async def unload_model(model_id: str) -> dict[str, str]:
        if service.active_model_id != model_id:
            raise RuntimeFault(_not_found("MODEL_NOT_LOADED", "此模型当前未加载"))
        return await service.unload_model()

    @app.delete("/internal/v1/models/{model_id}/registration", dependencies=[Depends(authenticate)])
    async def unregister_model(model_id: str) -> dict[str, bool]:
        if model_id == "builtin-fake-text":
            raise RuntimeFault(_not_found("MODEL_NOT_FOUND", "内置模型不可移除"))
        if service.active_model_id == model_id:
            await service.unload_model()
        model = service.models.pop(model_id, None)
        if model is None:
            raise RuntimeFault(_not_found("MODEL_NOT_FOUND", "找不到可移除的模型"))
        service.store.remove_model(model_id)
        return {"removed": True}

    @app.delete("/internal/v1/models/{model_id}/files", dependencies=[Depends(authenticate)])
    async def delete_model_files(model_id: str, confirm: bool = False) -> dict[str, bool]:
        if not confirm:
            raise HTTPException(status_code=400, detail="CONFIRMATION_REQUIRED")
        model = service.models.get(model_id)
        if model is None or model.source == "builtin":
            raise RuntimeFault(_not_found("MODEL_NOT_FOUND", "找不到可删除的本地模型"))
        path = Path(model.local_path).resolve()
        models_root = (
            Path(os.getenv("MLX_STUDIO_MODELS_DIR", Path.home() / "MLXModels"))
            .expanduser()
            .resolve()
        )
        if not path.is_dir() or not path.is_relative_to(models_root) or path == models_root:
            raise HTTPException(status_code=400, detail="MODEL_PATH_NOT_MANAGED")
        import shutil

        await asyncio.to_thread(shutil.rmtree, path)
        await unregister_model(model_id)
        return {"removed": True}

    @app.get("/internal/v1/conversations", dependencies=[Depends(authenticate)])
    async def list_conversations() -> list[dict[str, Any]]:
        return service.store.list_conversations()

    @app.post("/internal/v1/conversations", dependencies=[Depends(authenticate)])
    async def create_conversation(body: ConversationCreate) -> dict[str, Any]:
        return await service.create_conversation(body.title, body.model_id)

    @app.get("/internal/v1/conversations/{conversation_id}", dependencies=[Depends(authenticate)])
    async def get_conversation(conversation_id: str) -> dict[str, Any]:
        conversation = service.store.get_conversation(conversation_id)
        if conversation is None:
            raise RuntimeFault(_not_found("CONVERSATION_NOT_FOUND", "找不到此会话"))
        return conversation

    @app.patch("/internal/v1/conversations/{conversation_id}", dependencies=[Depends(authenticate)])
    async def patch_conversation(conversation_id: str, body: ConversationPatch) -> dict[str, bool]:
        if not service.store.rename_conversation(conversation_id, body.title):
            raise RuntimeFault(_not_found("CONVERSATION_NOT_FOUND", "找不到此会话"))
        return {"updated": True}

    @app.delete(
        "/internal/v1/conversations/{conversation_id}", dependencies=[Depends(authenticate)]
    )
    async def delete_conversation(conversation_id: str) -> dict[str, bool]:
        if not service.store.delete_conversation(conversation_id):
            raise RuntimeFault(_not_found("CONVERSATION_NOT_FOUND", "找不到此会话"))
        return {"deleted": True}

    @app.post(
        "/internal/v1/conversations/{conversation_id}/messages",
        dependencies=[Depends(authenticate)],
    )
    async def send_message(conversation_id: str, body: ChatMessageRequest) -> dict[str, str]:
        return await service.send_message(
            conversation_id,
            body.content,
            body.model_id,
            body.max_tokens,
            body.temperature,
            body.attachment_ids,
        )

    @app.post(
        "/internal/v1/conversations/{conversation_id}/regenerate",
        dependencies=[Depends(authenticate)],
    )
    async def regenerate(
        conversation_id: str, model_id: str, max_tokens: int = 512
    ) -> dict[str, str]:
        conversation = service.store.get_conversation(conversation_id)
        if conversation is None:
            raise RuntimeFault(_not_found("CONVERSATION_NOT_FOUND", "找不到此会话"))
        messages = conversation.get("messages", [])
        last_user = next((m for m in reversed(messages) if m["role"] == "user"), None)
        if last_user is None:
            raise RuntimeFault(_not_found("MESSAGE_NOT_FOUND", "没有可重新生成的用户消息"))
        replace_assistant_message_id = service.store.last_assistant_message_id(conversation_id)
        return await service.send_message(
            conversation_id,
            last_user["content"],
            model_id,
            max_tokens,
            0.7,
            persist_user_message=False,
            turn_id=str(last_user.get("turnId") or last_user["id"]),
            replace_assistant_message_id=replace_assistant_message_id,
        )

    @app.post(
        "/internal/v1/conversations/{conversation_id}/cancel", dependencies=[Depends(authenticate)]
    )
    async def cancel_conversation(conversation_id: str, job_id: str) -> dict[str, str]:
        return await service.cancel_job(job_id)

    @app.get("/internal/v1/jobs", dependencies=[Depends(authenticate)])
    async def list_jobs() -> list[dict[str, Any]]:
        return service.store.list_jobs()

    @app.post("/internal/v1/image-jobs", dependencies=[Depends(authenticate)])
    async def create_image_job(_: ImageJobRequest) -> dict[str, str]:
        raise RuntimeFault(_unavailable("ENGINE_NOT_AVAILABLE", "MFLUX Adapter 尚未通过基线验证"))

    @app.get("/internal/v1/events", dependencies=[Depends(authenticate)])
    async def event_stream(request: Request, after: int = 0):
        queue = await service.events.subscribe(after=max(0, after))

        async def stream_events():
            try:
                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15)
                        event_json = json.dumps(event.as_dict(), ensure_ascii=False)
                        yield f"id: {event.seq}\nevent: {event.type}\ndata: {event_json}\n\n"
                    except TimeoutError:
                        yield ": keep-alive\n\n"
            finally:
                service.events.unsubscribe(queue)

        return StreamingResponse(stream_events(), media_type="text/event-stream")

    if external_enabled:
        _register_openai_api(app, service, os.getenv("MLX_STUDIO_EXTERNAL_API_TOKEN", ""))
    return app


def _register_openai_api(app: FastAPI, service: RuntimeService, token: str) -> None:
    if not token:
        raise RuntimeError("External API requires its own token")

    async def external_auth(authorization: str | None = Header(default=None)) -> None:
        if authorization is None or not hmac.compare_digest(authorization, f"Bearer {token}"):
            raise HTTPException(status_code=401, detail="UNAUTHORIZED")

    @app.get("/v1/models", dependencies=[Depends(external_auth)])
    async def external_models() -> dict[str, object]:
        return {
            "object": "list",
            "data": [{"id": model["id"], "object": "model"} for model in service.list_models()],
        }

    @app.post("/v1/chat/completions", dependencies=[Depends(external_auth)])
    async def external_chat(body: dict[str, Any]) -> dict[str, object]:
        raise HTTPException(status_code=501, detail="STREAMING_COMPATIBILITY_NOT_AVAILABLE")


def _status_for_code(code: str) -> int:
    return 404 if code.endswith("NOT_FOUND") else 503 if code.endswith("NOT_AVAILABLE") else 400


def _not_found(code: str, message: str):
    from mlx_studio_runtime.domain.errors import RuntimeErrorInfo

    return RuntimeErrorInfo(code, message)


def _unavailable(code: str, message: str):
    from mlx_studio_runtime.domain.errors import RuntimeErrorInfo

    return RuntimeErrorInfo(code, message, retryable=True)


def _disk_free(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(path).free


def _counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


async def _pull_model(body: ModelPullRequest, service: RuntimeService) -> dict[str, str]:
    if "/" not in body.repo_id or body.repo_id.startswith("/"):
        raise HTTPException(status_code=400, detail="MODEL_REPO_ID_INVALID")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as error:
        raise RuntimeFault(
            _unavailable("DOWNLOAD_ADAPTER_UNAVAILABLE", "下载组件尚未安装")
        ) from error
    target_root = Path(os.getenv("MLX_STUDIO_MODELS_DIR", Path.home() / "MLXModels")).expanduser()
    target_root.mkdir(parents=True, exist_ok=True)
    try:
        model_path = await asyncio.to_thread(
            snapshot_download,
            repo_id=body.repo_id,
            revision=body.revision,
            local_dir=str(target_root / body.repo_id.replace("/", "--")),
        )
    except Exception as error:
        raise RuntimeFault(_unavailable("MODEL_DOWNLOAD_FAILED", "模型下载失败")) from error
    manifest = await service.scan_model(
        Path(model_path),
        source="huggingface",
        revision=body.revision,
        display_name=body.repo_id,
    )
    return {"modelId": str(manifest["id"]), "state": "available"}


def store_path_root(database_path: Path) -> Path:
    data_directory = database_path.parent
    app_directory = data_directory.parent if data_directory.name == "data" else data_directory
    return app_directory / "media"


async def _save_attachment(
    request: Request, filename: str, store: SQLiteStore, database_path: Path
) -> dict[str, Any]:
    max_bytes = 20 * 1024 * 1024
    attachment_id = str(uuid.uuid4())
    root = store_path_root(database_path)
    attachment_dir = root / "attachments"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    temp_path = attachment_dir / f".{attachment_id}.upload"
    digest = hashlib.sha256()
    header = bytearray()
    size = 0
    try:
        with temp_path.open("wb") as output:
            async for chunk in request.stream():
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="ATTACHMENT_TOO_LARGE")
                if len(header) < 16:
                    header.extend(chunk[: 16 - len(header)])
                digest.update(chunk)
                output.write(chunk)
        mime_type = _image_mime(bytes(header))
        if mime_type is None or size == 0:
            raise HTTPException(status_code=415, detail="IMAGE_FORMAT_UNSUPPORTED")
        safe_name = Path(filename.replace("\\", "/")).name[:180] or "image"
        relative_path = f"attachments/{attachment_id}"
        final_path = root / relative_path
        temp_path.replace(final_path)
        item = {
            "id": attachment_id,
            "sha256": digest.hexdigest(),
            "mimeType": mime_type,
            "sizeBytes": size,
            "relativePath": relative_path,
            "originalName": safe_name,
        }
        store.save_attachment(item)
        return {key: item[key] for key in ("id", "sha256", "mimeType", "sizeBytes", "originalName")}
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _image_mime(header: bytes) -> str | None:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None
