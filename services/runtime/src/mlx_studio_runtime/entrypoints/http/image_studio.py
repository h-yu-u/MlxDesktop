"""Image task, gallery, and authenticated local PNG endpoints."""

import secrets
from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from mlx_studio_runtime.adapters.image_files import artifact_path
from mlx_studio_runtime.application.runtime_service import RuntimeService
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.domain.image_generation import ImageParameters
from mlx_studio_runtime.domain.jobs import JobState


class ImageJobRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=10_000, pattern=r"\S")
    width: int = Field(default=512, ge=64, le=2048, multiple_of=16)
    height: int = Field(default=512, ge=64, le=2048, multiple_of=16)
    steps: int = Field(default=20, ge=1, le=100)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)


class ImageSnapshot(BaseModel):
    model_id: str
    model_name: str
    prompt: str
    width: int
    height: int
    steps: int
    seed: int
    simulated: bool


class ImageArtifactView(ImageSnapshot):
    id: str
    job_id: str
    created_at: int


class ImageJobView(ImageSnapshot):
    id: str
    state: JobState
    progress: int = Field(ge=0, le=100)
    created_at: int
    error_code: str | None
    artifact_id: str | None


def register_image_studio_routes(
    app: FastAPI,
    service: RuntimeService,
    authenticate: Callable[..., Awaitable[None]],
) -> None:
    dependencies = [Depends(authenticate)]

    @app.post("/internal/v1/image-jobs", dependencies=dependencies, response_model=ImageJobView)
    async def create_image_job(body: ImageJobRequest) -> ImageJobView:
        parameters = ImageParameters(
            model_id=body.model_id,
            prompt=body.prompt.strip(),
            width=body.width,
            height=body.height,
            steps=body.steps,
            seed=body.seed if body.seed is not None else secrets.randbits(32),
        )
        return ImageJobView.model_validate(await service.images.create(parameters))

    @app.get(
        "/internal/v1/image-jobs", dependencies=dependencies, response_model=list[ImageJobView]
    )
    async def list_image_jobs() -> list[ImageJobView]:
        return [ImageJobView.model_validate(item) for item in service.images.list_jobs()]

    @app.get(
        "/internal/v1/image-jobs/{job_id}", dependencies=dependencies, response_model=ImageJobView
    )
    async def get_image_job(job_id: str) -> ImageJobView:
        return ImageJobView.model_validate(service.images.get_job(job_id))

    @app.post("/internal/v1/image-jobs/{job_id}/cancel", dependencies=dependencies)
    async def cancel_image_job(job_id: str) -> dict[str, str]:
        service.images.get_job(job_id)
        return await service.cancel_job(job_id)

    @app.get(
        "/internal/v1/image-artifacts",
        dependencies=dependencies,
        response_model=list[ImageArtifactView],
    )
    async def image_history(
        limit: int = Query(default=24, ge=1, le=60),
        offset: int = Query(default=0, ge=0),
    ) -> list[ImageArtifactView]:
        return [
            ImageArtifactView.model_validate(item)
            for item in service.store.images.list_artifacts(limit, offset)
        ]

    @app.get("/internal/v1/image-artifacts/{artifact_id}/content", dependencies=dependencies)
    async def image_content(artifact_id: str) -> FileResponse:
        return _image_content(service, artifact_id)


def _image_content(service: RuntimeService, artifact_id: str) -> FileResponse:
    item = service.store.images.get(artifact_id)
    if item is None:
        raise RuntimeFault(RuntimeErrorInfo("IMAGE_ARTIFACT_NOT_FOUND", "找不到此作品"))
    try:
        path = artifact_path(service.store.media_path, item["relative_path"])
    except ValueError as error:
        raise RuntimeFault(RuntimeErrorInfo("IMAGE_PATH_INVALID", "作品路径无效")) from error
    if not path.is_file():
        raise RuntimeFault(RuntimeErrorInfo("IMAGE_FILE_NOT_FOUND", "作品文件已不存在"))
    return FileResponse(
        path,
        media_type="image/png",
        filename=f"mlx-studio-{artifact_id}.png",
        content_disposition_type="inline",
    )
