"""Runtime use cases: model lifecycle, chat jobs and event publication."""

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from mlx_studio_runtime.adapters.event_hub import EventHub
from mlx_studio_runtime.adapters.persistence.sqlite_store import SQLiteStore
from mlx_studio_runtime.adapters.worker_host import WorkerHost, WorkerProtocolError
from mlx_studio_runtime.application.chat_support import (
    attachment_paths,
    conversation_context,
    validate_attachments,
)
from mlx_studio_runtime.application.image_generation_service import ImageGenerationService
from mlx_studio_runtime.application.job_lifecycle import JobLifecycle
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.domain.image_generation import fake_image_manifest_dict
from mlx_studio_runtime.domain.jobs import Job, JobEvent, JobState, terminal_state
from mlx_studio_runtime.domain.models import (
    ModelManifest,
    ModelSource,
    fake_text_manifest,
    manifest_from_dict,
    manifest_from_directory,
)
from mlx_studio_runtime.domain.runtime_state import RuntimeState

LOGGER = logging.getLogger("mlx_studio.runtime")


class RuntimeService:
    def __init__(self, store: SQLiteStore, runtime_source: Path) -> None:
        self.store = store
        self.runtime_source = runtime_source
        self.events = EventHub()
        self.models: dict[str, ModelManifest] = {}
        self.job_lifecycle = JobLifecycle(self.store, self.events)
        self.jobs = self.job_lifecycle.items
        self.job_tasks: dict[str, asyncio.Task[None]] = {}
        self.worker: WorkerHost | None = None
        self.active_model_id: str | None = None
        self.active_job_id: str | None = None
        self.generation_lock = asyncio.Lock()
        self.state = RuntimeState.READY
        self.started_at = time.monotonic()
        self.worker_restarts = 0
        self.store.recover_interrupted_jobs("RUNTIME_RESTARTED")
        self._seed_fake_model()
        self._restore_models()
        self.images = ImageGenerationService(self)

    def _seed_fake_model(self) -> None:
        manifest = fake_text_manifest()
        self.models[manifest.id] = manifest
        self.store.upsert_model(manifest.to_dict(), "available")
        image_manifest = manifest_from_dict(fake_image_manifest_dict())
        self.models[image_manifest.id] = image_manifest
        self.store.upsert_model(image_manifest.to_dict(), "available")

    def _restore_models(self) -> None:
        for item in self.store.list_models():
            try:
                manifest = manifest_from_dict(item)
            except (KeyError, TypeError, ValueError):
                continue
            self.models[manifest.id] = manifest
            if item.get("state") in {"loaded", "loading", "unloading"}:
                self.store.update_model_state(manifest.id, "available")

    def list_models(self) -> list[dict[str, Any]]:
        return self.store.list_models()

    async def scan_model(
        self,
        path: Path,
        source: ModelSource = "local",
        revision: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        try:
            manifest = manifest_from_directory(
                path,
                source=source,
                revision=revision,
                display_name=display_name,
            )
        except (OSError, ValueError) as error:
            raise RuntimeFault(
                RuntimeErrorInfo("MODEL_METADATA_INVALID", "无法读取模型静态元数据")
            ) from error
        self.models[manifest.id] = manifest
        result = manifest.to_dict()
        self.store.upsert_model(result, "available")
        await self.events.publish("model.discovered", {"model": result})
        return result

    async def load_model(self, model_id: str) -> dict[str, Any]:
        async with self.generation_lock:
            return await self._load_model(model_id)

    async def _load_model(self, model_id: str) -> dict[str, Any]:
        manifest = self.models.get(model_id)
        if manifest is None:
            raise RuntimeFault(RuntimeErrorInfo("MODEL_NOT_FOUND", "找不到此模型"))
        if manifest.engine not in {"fake", "mlx-lm", "mlx-vlm", "mflux"}:
            raise RuntimeFault(
                RuntimeErrorInfo(
                    "ENGINE_NOT_AVAILABLE",
                    "该模型引擎尚未接入 Runtime Worker",
                    details={"engine": manifest.engine},
                )
            )
        if self.active_model_id == model_id and self.worker is not None:
            return {"modelId": model_id, "state": "loaded"}
        await self._stop_worker()
        self.store.update_model_state(model_id, "loading")
        await self.events.publish("model.loading", {"model_id": model_id})
        worker = WorkerHost(self.runtime_source, self.store.media_path / "images")
        self.worker = worker
        try:
            await worker.load(manifest.to_dict())
        except Exception as error:
            await worker.stop()
            if self.worker is worker:
                self.worker = None
            self.store.update_model_state(model_id, "error")
            self.state = RuntimeState.DEGRADED
            await self.events.publish("runtime.degraded", {"reason": "worker_load_failed"})
            raise RuntimeFault(
                RuntimeErrorInfo("MODEL_LOAD_FAILED", "模型加载失败", True)
            ) from error
        self.active_model_id = model_id
        self.store.update_model_state(model_id, "loaded")
        self.state = RuntimeState.READY
        await self.events.publish("model.loaded", {"model_id": model_id})
        return {"modelId": model_id, "state": "loaded"}

    async def unload_model(self) -> dict[str, str]:
        async with self.generation_lock:
            await self._stop_worker()
        return {"state": "available"}

    async def create_conversation(self, title: str, model_id: str | None) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "title": title,
            "modelId": model_id,
            "parameters": {},
        }
        self.store.save_conversation(item)
        return self.store.get_conversation(item["id"]) or item

    async def send_message(
        self,
        conversation_id: str,
        content: str,
        model_id: str,
        max_tokens: int,
        temperature: float,
        attachment_ids: list[str] | None = None,
        persist_user_message: bool = True,
        turn_id: str | None = None,
        replace_assistant_message_id: str | None = None,
    ) -> dict[str, str]:
        conversation = self.store.get_conversation(conversation_id)
        if conversation is None:
            raise RuntimeFault(RuntimeErrorInfo("CONVERSATION_NOT_FOUND", "找不到此会话"))
        selected_model = self.models.get(model_id)
        if selected_model is None:
            raise RuntimeFault(RuntimeErrorInfo("MODEL_NOT_FOUND", "找不到此模型"))
        if "text" not in selected_model.output_modalities:
            raise RuntimeFault(
                RuntimeErrorInfo("MODEL_CAPABILITY_INVALID", "请选择文本或多模态对话模型")
            )
        attachment_ids = attachment_ids or []
        validate_attachments(selected_model, attachment_ids)
        image_paths = attachment_paths(self.store, attachment_ids)
        turn_id = turn_id or str(uuid.uuid4())
        if persist_user_message:
            self.store.save_message(
                {
                    "id": turn_id,
                    "turnId": turn_id,
                    "conversationId": conversation_id,
                    "role": "user",
                    "content": content,
                    "parameters": {"maxTokens": max_tokens, "temperature": temperature},
                    "attachmentIds": attachment_ids,
                }
            )
        job = Job(str(uuid.uuid4()), "chat", JobState.QUEUED, model_id)
        await self.job_lifecycle.register(
            job,
            {"conversationId": conversation_id, "maxTokens": max_tokens},
        )
        task = asyncio.create_task(
            self._run_chat_job(
                job,
                conversation_id,
                content,
                max_tokens,
                temperature,
                image_paths,
                turn_id,
                replace_assistant_message_id,
            )
        )
        self.job_tasks[job.id] = task
        task.add_done_callback(
            lambda completed, job_id=job.id: self._forget_job_task(job_id, completed)
        )
        return {"jobId": job.id, "state": job.state.value}

    async def cancel_job(self, job_id: str) -> dict[str, str]:
        job = self.jobs.get(job_id)
        if job is None:
            raise RuntimeFault(RuntimeErrorInfo("JOB_NOT_FOUND", "找不到此任务"))
        if terminal_state(job.state) or job.state is JobState.CANCELLING:
            return {"jobId": job_id, "state": job.state.value}
        await self.job_lifecycle.transition(job_id, JobEvent.CANCEL_REQUESTED)
        if self.worker and self.active_job_id == job_id:
            await self.worker.cancel(job_id)
        task = self.job_tasks.get(job_id)
        if task and self.active_job_id != job_id:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if task and self.active_job_id == job_id:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5)
            except TimeoutError:
                await self._stop_worker()
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        if self.jobs[job_id].state is JobState.CANCELLING and (not task or task.done()):
            await self.job_lifecycle.finish(job_id, JobEvent.CANCEL_COMPLETE)
        return {"jobId": job_id, "state": self.jobs[job_id].state.value}

    async def restart_worker(self) -> dict[str, str]:
        async with self.generation_lock:
            model_id = self.active_model_id
            await self._stop_worker()
            self.worker_restarts += 1
            if model_id:
                await self._load_model(model_id)
            self.state = RuntimeState.READY
            return {"state": "ready"}

    async def _run_chat_job(
        self,
        initial_job: Job,
        conversation_id: str,
        content: str,
        max_tokens: int,
        temperature: float,
        image_paths: list[str],
        turn_id: str,
        replace_assistant_message_id: str | None,
    ) -> None:
        job_id = initial_job.id
        try:
            async with self.generation_lock:
                if self.jobs[job_id].state is JobState.CANCELLING:
                    await self.job_lifecycle.finish(job_id, JobEvent.CANCEL_COMPLETE)
                    return
                self.active_job_id = job_id
                messages = conversation_context(self.store, conversation_id, turn_id)
                if self.active_model_id != initial_job.model_id or self.worker is None:
                    await self._load_model(initial_job.model_id or "")
                await self._run_chat_job_serial(
                    initial_job,
                    conversation_id,
                    content,
                    max_tokens,
                    temperature,
                    image_paths,
                    messages,
                    turn_id,
                    replace_assistant_message_id,
                )
        except asyncio.CancelledError:
            await self.job_lifecycle.finish_failed_or_cancelled(job_id, "RUNTIME_SHUTDOWN")
            raise
        except RuntimeFault as error:
            await self.job_lifecycle.finish_failed_or_cancelled(job_id, error.info.code)
        except Exception:
            LOGGER.exception("Unhandled chat job failure", extra={"job_id": job_id})
            await self.job_lifecycle.finish_failed_or_cancelled(job_id, "INFERENCE_FAILED")
        finally:
            if self.active_job_id == job_id:
                self.active_job_id = None

    async def _run_chat_job_serial(
        self,
        initial_job: Job,
        conversation_id: str,
        content: str,
        max_tokens: int,
        temperature: float,
        image_paths: list[str],
        messages: list[dict[str, str]],
        turn_id: str,
        replace_assistant_message_id: str | None,
    ) -> None:
        job_id = initial_job.id
        if self.jobs[job_id].state is JobState.CANCELLING:
            await self.job_lifecycle.finish(job_id, JobEvent.CANCEL_COMPLETE)
            return
        await self.job_lifecycle.transition(job_id, JobEvent.PREPARE)
        await self.job_lifecycle.transition(job_id, JobEvent.START)
        if self.worker is None:
            raise WorkerProtocolError("worker is unavailable")
        output: list[str] = []
        async for event in self.worker.generate(
            job_id,
            content,
            max_tokens,
            temperature,
            image_paths,
            messages,
        ):
            event_type = event["type"]
            payload = event["payload"]
            if event_type == "generation.delta":
                delta = str(payload.get("text", ""))
                output.append(delta)
                await self.events.publish(event_type, {"job_id": job_id, "text": delta})
            elif event_type == "generation.cancelled":
                await self.job_lifecycle.finish(job_id, JobEvent.CANCEL_COMPLETE)
                return
            elif event_type == "generation.failed":
                code = str(payload.get("error_code", "INFERENCE_FAILED"))
                raise RuntimeFault(RuntimeErrorInfo(code, "模型推理失败", True))
        if self.jobs[job_id].state is JobState.CANCELLING:
            await self.job_lifecycle.finish(job_id, JobEvent.CANCEL_COMPLETE)
            return
        self.store.save_message(
            {
                "id": str(uuid.uuid4()),
                "turnId": turn_id,
                "conversationId": conversation_id,
                "role": "assistant",
                "content": "".join(output),
                "modelSnapshot": self.models[initial_job.model_id or ""].to_dict(),
                "parameters": {"maxTokens": max_tokens, "temperature": temperature},
            },
            replace_message_id=replace_assistant_message_id,
        )
        await self.job_lifecycle.finish(job_id, JobEvent.COMPLETE)

    async def _stop_worker(self) -> None:
        model_id = self.active_model_id
        if self.worker:
            await self.worker.stop()
        self.worker = None
        self.active_model_id = None
        if model_id:
            self.store.update_model_state(model_id, "available")
            await self.events.publish("model.unloaded", {"model_id": model_id})

    def _forget_job_task(self, job_id: str, task: asyncio.Task[None]) -> None:
        if self.job_tasks.get(job_id) is task:
            self.job_tasks.pop(job_id, None)
        if not task.cancelled():
            exception = task.exception()
            if exception is not None:
                LOGGER.error("Runtime task escaped its guard: %r", exception)

    async def close(self) -> None:
        tasks = tuple(self.job_tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self._stop_worker()
        self.store.close()
