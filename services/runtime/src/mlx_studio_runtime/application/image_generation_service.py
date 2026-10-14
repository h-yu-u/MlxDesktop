"""Image task orchestration sharing the Runtime generation lock and job lifecycle."""

import asyncio
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mlx_studio_runtime.adapters.image_files import commit_image, image_output_path, validate_png
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.domain.image_generation import ImageParameters
from mlx_studio_runtime.domain.jobs import Job, JobEvent, JobState

if TYPE_CHECKING:
    from mlx_studio_runtime.application.runtime_service import RuntimeService


class ImageGenerationService:
    def __init__(self, runtime: "RuntimeService") -> None:
        self.runtime = runtime
        self.progress: dict[str, int] = {}

    async def create(self, parameters: ImageParameters) -> dict[str, Any]:
        model = self.runtime.models.get(parameters.model_id)
        if model is None:
            raise RuntimeFault(RuntimeErrorInfo("MODEL_NOT_FOUND", "请选择已下载的生图模型"))
        if model.task != "image-generation" or "image" not in model.output_modalities:
            raise RuntimeFault(RuntimeErrorInfo("IMAGE_MODEL_INVALID", "此模型不支持图片生成"))
        job = Job(str(uuid.uuid4()), "image", JobState.QUEUED, model.id)
        snapshot = dict(
            parameters.to_dict(), model_name=model.display_name, simulated=model.engine == "fake"
        )
        await self.runtime.job_lifecycle.register(job, snapshot)
        task = asyncio.create_task(self._run(job, parameters, snapshot))
        self.runtime.job_tasks[job.id] = task
        task.add_done_callback(lambda completed: self.runtime._forget_job_task(job.id, completed))
        return self.get_job(job.id)

    def get_job(self, job_id: str) -> dict[str, Any]:
        rows = self.runtime.store.images.jobs(job_id)
        if not rows:
            raise RuntimeFault(RuntimeErrorInfo("IMAGE_JOB_NOT_FOUND", "找不到图片生成任务"))
        return self._view(rows[0])

    def list_jobs(self) -> list[dict[str, Any]]:
        return [self._view(item) for item in self.runtime.store.images.jobs()]

    def _view(self, item: dict[str, Any]) -> dict[str, Any]:
        return dict(
            item, progress=100 if item["state"] == "succeeded" else self.progress.get(item["id"], 0)
        )

    async def _run(
        self, job: Job, parameters: ImageParameters, snapshot: dict[str, object]
    ) -> None:
        output: Path | None = None
        try:
            output = image_output_path(self.runtime.store.media_path, job.id)
            await self._run_serial(job, parameters, output, snapshot)
        except asyncio.CancelledError:
            await self.runtime.job_lifecycle.finish_failed_or_cancelled(job.id, "RUNTIME_SHUTDOWN")
            raise
        except RuntimeFault as error:
            await self.runtime.job_lifecycle.finish_failed_or_cancelled(job.id, error.info.code)
        except Exception:  # Task boundary; retain a terminal state without logging prompts.
            await self.runtime.job_lifecycle.finish_failed_or_cancelled(
                job.id, "IMAGE_GENERATION_FAILED"
            )
        finally:
            if output:
                output.unlink(missing_ok=True)
            if self.runtime.active_job_id == job.id:
                self.runtime.active_job_id = None
            self.progress.pop(job.id, None)

    async def _run_serial(
        self,
        job: Job,
        parameters: ImageParameters,
        output: Path,
        snapshot: dict[str, object],
    ) -> None:
        async with self.runtime.generation_lock:
            try:
                async with asyncio.timeout(3600):
                    if self._cancelled(job.id):
                        await self.runtime.job_lifecycle.finish(job.id, JobEvent.CANCEL_COMPLETE)
                        return
                    self.runtime.active_job_id = job.id
                    await self.runtime.job_lifecycle.transition(job.id, JobEvent.PREPARE)
                    if (
                        self.runtime.active_model_id != parameters.model_id
                        or self.runtime.worker is None
                    ):
                        await self.runtime._load_model(parameters.model_id)
                    await self._generate(job, parameters, output, snapshot)
            except BaseException:  # Stop resources while still holding the generation lock.
                if self.runtime.active_job_id == job.id:
                    await self.runtime._stop_worker()
                raise

    async def _generate(
        self,
        job: Job,
        parameters: ImageParameters,
        output: Path,
        snapshot: dict[str, object],
    ) -> None:
        if self._cancelled(job.id):
            await self.runtime.job_lifecycle.finish(job.id, JobEvent.CANCEL_COMPLETE)
            return
        worker = self.runtime.worker
        if worker is None:
            raise RuntimeError("IMAGE_WORKER_UNAVAILABLE")
        await self.runtime.job_lifecycle.transition(job.id, JobEvent.START)
        completed = False
        async for event in worker.generate_image(job.id, parameters.to_dict(), output):
            kind, payload = event["type"], event["payload"]
            if kind == "image.progress":
                self.progress[job.id] = min(
                    99, max(0, int(payload["step"]) * 100 // parameters.steps)
                )
                await self.runtime.events.publish(kind, payload)
            elif kind == "generation.cancelled":
                await self.runtime.job_lifecycle.finish_failed_or_cancelled(
                    job.id, "IMAGE_CANCELLED"
                )
                return
            elif kind == "generation.failed":
                raise RuntimeError("IMAGE_GENERATION_FAILED")
            elif kind == "generation.completed":
                completed = True
        if self._cancelled(job.id):
            await self.runtime.job_lifecycle.finish(job.id, JobEvent.CANCEL_COMPLETE)
            return
        if not completed:
            raise RuntimeError("IMAGE_WORKER_ENDED_EARLY")
        await self._save_output(job, parameters, output, snapshot)

    async def _save_output(
        self,
        job: Job,
        parameters: ImageParameters,
        output: Path,
        snapshot: dict[str, object],
    ) -> None:
        await asyncio.to_thread(validate_png, output, parameters.width, parameters.height)
        if self._cancelled(job.id):
            await self.runtime.job_lifecycle.finish(job.id, JobEvent.CANCEL_COMPLETE)
            return
        artifact_id = str(uuid.uuid4())
        relative = commit_image(self.runtime.store.media_path, output, artifact_id)
        try:
            self.runtime.store.images.save(artifact_id, job.id, relative, snapshot)
        except Exception:
            (self.runtime.store.media_path / relative).unlink(missing_ok=True)
            raise
        await self.runtime.job_lifecycle.finish(job.id, JobEvent.COMPLETE)
        await self.runtime.events.publish(
            "image.created", {"job_id": job.id, "artifact_id": artifact_id}
        )

    def _cancelled(self, job_id: str) -> bool:
        return self.runtime.jobs[job_id].state is JobState.CANCELLING
