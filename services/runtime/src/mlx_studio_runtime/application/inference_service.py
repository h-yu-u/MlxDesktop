"""Each provider call obtains one normal inference lease, never a CodingRun lease."""

import asyncio
import uuid
from typing import Any

from mlx_studio_runtime.application.ports import JobAdmission, StructuredInference
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.domain.inference import validate_context
from mlx_studio_runtime.domain.jobs import Job, JobEvent, JobState
from mlx_studio_runtime.domain.models import ModelManifest


class InferenceService:
    def __init__(
        self,
        models: dict[str, ModelManifest],
        scheduler: JobAdmission,
        inference: StructuredInference,
    ) -> None:
        self.models, self.scheduler, self.inference = models, scheduler, inference

    async def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        model_id = str(request["model"])
        try:
            validate_context(request["messages"], request["tools"])
        except (ValueError, KeyError, TypeError) as error:
            raise RuntimeFault(RuntimeErrorInfo("INFERENCE_CONTEXT_INVALID", str(error))) from error
        model = self.models.get(model_id)
        if model is None or "text" not in model.output_modalities:
            raise RuntimeFault(RuntimeErrorInfo("MODEL_NOT_FOUND", "请选择文本模型"))
        self.scheduler.check_admission(model_id)
        job = Job(str(uuid.uuid4()), "coding-inference", JobState.QUEUED, model_id)
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        await self.scheduler.lifecycle.register(job, {"kind": "coding-inference"})

        async def execute() -> None:
            await self.scheduler.lifecycle.transition(job.id, JobEvent.START)
            async for event in self.inference.infer(job.id, request):
                if event["type"] == "generation.result" and not future.done():
                    future.set_result(event["payload"])
                if event["type"] == "generation.failed":
                    raise RuntimeFault(
                        RuntimeErrorInfo(
                            str(event["payload"].get("error_code", "INFERENCE_FAILED")),
                            "结构化推理失败",
                        )
                    )
                if event["type"] == "generation.cancelled":
                    await self.scheduler.lifecycle.finish_failed_or_cancelled(job.id, "CANCELLED")
                    return
            await self.scheduler.lifecycle.finish(job.id, JobEvent.COMPLETE)

        task = self.scheduler.schedule(job, execute)

        def settled(_: asyncio.Task[None]) -> None:
            if not future.done():
                code = self.scheduler.lifecycle.get(job.id).error_code or "INFERENCE_CANCELLED"
                future.set_exception(RuntimeFault(RuntimeErrorInfo(code, "结构化推理未完成")))

        task.add_done_callback(settled)
        try:
            result = await future
            await asyncio.shield(task)
            return result
        except asyncio.CancelledError:
            await self.scheduler.cancel(job.id)
            raise
