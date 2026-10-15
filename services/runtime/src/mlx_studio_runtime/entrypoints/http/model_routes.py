"""HTTP protocol adaptation; business behavior lives in application use cases."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from mlx_studio_runtime.composition_root import RuntimeApplication
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.entrypoints.http.contracts import (
    ModelPathRequest,
    ModelPullRequest,
    ModelView,
)
from mlx_studio_runtime.entrypoints.http.model_catalog import register_model_catalog_routes


def _not_found(code: str, message: str) -> RuntimeErrorInfo:
    return RuntimeErrorInfo(code, message)


def register_model_routes(
    app: FastAPI, service: RuntimeApplication, authenticate: Callable[..., Awaitable[None]]
) -> None:
    @app.get(
        "/internal/v1/models", dependencies=[Depends(authenticate)], response_model=list[ModelView]
    )
    async def list_models() -> list[dict[str, Any]]:
        return service.catalog.list_models()

    register_model_catalog_routes(app, authenticate)

    @app.get(
        "/internal/v1/models/{model_id}",
        dependencies=[Depends(authenticate)],
        response_model=ModelView,
    )
    async def get_model(model_id: str) -> dict[str, Any]:
        model = next(
            (model for model in service.catalog.list_models() if model["id"] == model_id), None
        )
        if model is None:
            raise RuntimeFault(_not_found("MODEL_NOT_FOUND", "找不到此模型"))
        return model

    @app.post("/internal/v1/models/scan", dependencies=[Depends(authenticate)])
    async def scan_model(body: ModelPathRequest) -> dict[str, Any]:
        return await service.catalog.scan_model(Path(body.path))

    @app.post("/internal/v1/models/import", dependencies=[Depends(authenticate)])
    async def import_model(body: ModelPathRequest) -> dict[str, Any]:
        return await service.catalog.scan_model(Path(body.path))

    @app.post("/internal/v1/models/pull", dependencies=[Depends(authenticate)])
    async def pull_model(body: ModelPullRequest) -> dict[str, str]:
        return await service.downloads.pull(body.repo_id, body.revision)

    @app.post("/internal/v1/attachments", dependencies=[Depends(authenticate)])
    async def upload_attachment(request: Request, filename: str = "image") -> dict[str, Any]:
        return await service.attachments.upload(request.stream(), filename)

    @app.get("/internal/v1/attachments/{attachment_id}", dependencies=[Depends(authenticate)])
    async def read_attachment(attachment_id: str):
        path, item = service.attachments.read(attachment_id)
        return FileResponse(path, media_type=item["mimeType"], filename=item["originalName"])

    @app.post("/internal/v1/models/{model_id}/load", dependencies=[Depends(authenticate)])
    async def load_model(model_id: str) -> dict[str, str]:
        return await service.controls.load(model_id)

    @app.post("/internal/v1/models/{model_id}/unload", dependencies=[Depends(authenticate)])
    async def unload_model(model_id: str) -> dict[str, str]:
        return await service.controls.unload(model_id)

    @app.delete("/internal/v1/models/{model_id}/registration", dependencies=[Depends(authenticate)])
    async def unregister_model(model_id: str) -> dict[str, bool]:
        return await service.model_removal.execute(model_id)

    @app.delete("/internal/v1/models/{model_id}/files", dependencies=[Depends(authenticate)])
    async def delete_model_files(model_id: str, confirm: bool = False) -> dict[str, bool]:
        if not confirm:
            raise HTTPException(status_code=400, detail="CONFIRMATION_REQUIRED")
        return await service.model_removal.execute(model_id, delete_files=True)
