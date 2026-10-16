"""Owns the loaded model and Worker; only the scheduler grants execution leases."""

from collections.abc import Callable
from typing import Any

from mlx_studio_runtime.application.ports import EventPublisher, InferenceWorker, ModelRepository
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.domain.models import ModelManifest
from mlx_studio_runtime.domain.runtime_state import RuntimeState


class ModelRuntime:
    def __init__(
        self,
        models: dict[str, ModelManifest],
        repository: ModelRepository,
        events: EventPublisher,
        create_worker: Callable[[], InferenceWorker],
    ) -> None:
        self.models = models
        self.repository = repository
        self.events = events
        self.create_worker = create_worker
        self.worker: InferenceWorker | None = None
        self.active_model_id: str | None = None
        self.state = RuntimeState.READY
        self.worker_restarts = 0

    async def load(self, model_id: str) -> dict[str, Any]:
        manifest = self.models.get(model_id)
        if manifest is None:
            raise RuntimeFault(RuntimeErrorInfo("MODEL_NOT_FOUND", "找不到此模型"))
        if manifest.engine not in {"fake", "mlx-lm", "mlx-vlm", "mflux", "mlx-audio"}:
            raise RuntimeFault(
                RuntimeErrorInfo(
                    "ENGINE_NOT_AVAILABLE",
                    "该模型引擎尚未接入 Runtime Worker",
                    details={"engine": manifest.engine},
                )
            )
        if self.active_model_id == model_id and self.worker is not None:
            return {"modelId": model_id, "state": "loaded"}
        await self.stop()
        self.repository.update_state(model_id, "loading")
        await self.events.publish("model.loading", {"model_id": model_id})
        worker = self.create_worker()
        self.worker = worker
        try:
            await worker.load(manifest.to_dict())
        except Exception as error:
            await worker.stop()
            if self.worker is worker:
                self.worker = None
            self.repository.update_state(model_id, "error")
            self.state = RuntimeState.DEGRADED
            await self.events.publish("runtime.degraded", {"reason": "worker_load_failed"})
            code = str(getattr(error, "code", "MODEL_LOAD_FAILED"))
            if code == "WORKER_COMMAND_FAILED":
                code = "MODEL_LOAD_FAILED"
            raise RuntimeFault(RuntimeErrorInfo(code, "模型加载失败", True)) from error
        self.active_model_id = model_id
        self.repository.update_state(model_id, "loaded")
        self.state = RuntimeState.READY
        await self.events.publish("model.loaded", {"model_id": model_id})
        return {"modelId": model_id, "state": "loaded"}

    async def stop(self) -> None:
        model_id = self.active_model_id
        if self.worker:
            await self.worker.stop()
        self.worker = None
        self.active_model_id = None
        if model_id:
            self.repository.update_state(model_id, "available")
            await self.events.publish("model.unloaded", {"model_id": model_id})
