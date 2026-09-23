"""Runtime use cases: model lifecycle, chat jobs and event publication."""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any

from mlx_studio_runtime.adapters.event_hub import EventHub
from mlx_studio_runtime.adapters.persistence.sqlite_store import SQLiteStore
from mlx_studio_runtime.adapters.worker_host import WorkerHost, WorkerProtocolError
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.domain.jobs import Job, JobEvent, JobState, transition_job
from mlx_studio_runtime.domain.models import (
    ModelManifest,
    fake_text_manifest,
    manifest_from_dict,
    manifest_from_directory,
)
from mlx_studio_runtime.domain.runtime_state import RuntimeState


class RuntimeService:
    def __init__(self, store: SQLiteStore, runtime_source: Path) -> None:
        self.store = store
        self.runtime_source = runtime_source
        self.events = EventHub()
        self.models: dict[str, ModelManifest] = {}
        self.jobs: dict[str, Job] = {}
        self.job_tasks: dict[str, asyncio.Task[None]] = {}
        self.worker: WorkerHost | None = None
        self.active_model_id: str | None = None
        self.active_job_id: str | None = None
        self.generation_lock = asyncio.Lock()
        self.state = RuntimeState.READY
        self.started_at = time.monotonic()
        self._seed_fake_model()
        for item in self.store.list_models():
            try:
                manifest = manifest_from_dict(item)
            except (KeyError, TypeError, ValueError):
                continue
            self.models[manifest.id] = manifest

    def _seed_fake_model(self) -> None:
        manifest = fake_text_manifest()
        self.models[manifest.id] = manifest
        self.store.upsert_model(manifest.to_dict(), "available")

    def list_models(self) -> list[dict[str, Any]]:
        return self.store.list_models()

    async def scan_model(self, path: Path) -> dict[str, Any]:
        try:
            manifest = manifest_from_directory(path)
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
        if manifest.engine not in {"fake", "mlx-lm", "mlx-vlm"}:
            raise RuntimeFault(
                RuntimeErrorInfo(
                    "ENGINE_NOT_AVAILABLE",
                    "该模型引擎尚未接入 Runtime Worker",
                    details={"engine": manifest.engine},
                )
            )
        await self._stop_worker()
        await self.events.publish("model.loading", {"model_id": model_id})
        worker = WorkerHost(self.runtime_source)
        try:
            await worker.load(manifest.to_dict())
        except Exception as error:
            await worker.stop()
            self.state = RuntimeState.DEGRADED
            await self.events.publish("runtime.degraded", {"reason": "worker_load_failed"})
            raise RuntimeFault(
                RuntimeErrorInfo("MODEL_LOAD_FAILED", "模型加载失败", True)
            ) from error
        self.worker = worker
        self.active_model_id = model_id
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
    ) -> dict[str, str]:
        conversation = self.store.get_conversation(conversation_id)
        if conversation is None:
            raise RuntimeFault(RuntimeErrorInfo("CONVERSATION_NOT_FOUND", "找不到此会话"))
        if model_id not in self.models:
            raise RuntimeFault(RuntimeErrorInfo("MODEL_NOT_FOUND", "找不到此模型"))
        selected_model = self.models[model_id]
        attachment_ids = attachment_ids or []
        if attachment_ids and "image" not in selected_model.input_modalities:
            raise RuntimeFault(
                RuntimeErrorInfo("MODEL_INPUT_UNSUPPORTED", "当前模型不支持图片输入")
            )
        if attachment_ids and selected_model.engine != "mlx-vlm":
            raise RuntimeFault(
                RuntimeErrorInfo("ENGINE_NOT_AVAILABLE", "此图片模型尚未通过 Runtime 验证")
            )
        if len(attachment_ids) > 1 and not selected_model.capabilities.multi_image:
            raise RuntimeFault(
                RuntimeErrorInfo("MODEL_INPUT_UNSUPPORTED", "当前模型仅声明支持单图片输入")
            )
        attachments = self.store.get_attachments(attachment_ids)
        if attachments is None:
            raise RuntimeFault(RuntimeErrorInfo("ATTACHMENT_NOT_FOUND", "请求包含不存在的附件"))
        image_paths = [
            str((self.store.media_path / item["relativePath"]).resolve()) for item in attachments
        ]
        turn_id = turn_id or str(uuid.uuid4())
        user_message = {
            "id": turn_id,
            "turnId": turn_id,
            "conversationId": conversation_id,
            "role": "user",
            "content": content,
            "parameters": {"maxTokens": max_tokens, "temperature": temperature},
            "attachmentIds": attachment_ids,
        }
        if persist_user_message:
            self.store.save_message(user_message)
        job = Job(str(uuid.uuid4()), "chat", JobState.QUEUED, model_id)
        self.jobs[job.id] = job
        self.store.save_job(
            {
                "id": job.id,
                "kind": job.kind,
                "state": job.state.value,
                "modelId": model_id,
                "request": {"conversationId": conversation_id, "maxTokens": max_tokens},
            }
        )
        await self.events.publish("job.updated", {"job_id": job.id, "state": job.state.value})
        task = asyncio.create_task(
            self._run_chat_job(
                job,
                conversation_id,
                content,
                max_tokens,
                temperature,
                image_paths,
                turn_id,
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
        self.jobs[job_id] = transition_job(job, JobEvent.CANCEL_REQUESTED)
        self.store.update_job(job_id, JobState.CANCELLING.value)
        await self.events.publish("job.updated", {"job_id": job_id, "state": "cancelling"})
        if self.worker and self.active_job_id == job_id:
            await self.worker.cancel(job_id)
        task = self.job_tasks.get(job_id)
        if task and self.active_job_id == job_id:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5)
            except TimeoutError:
                await self._stop_worker()
                current = self.jobs[job_id]
                if current.state is JobState.CANCELLING:
                    await self._finish_job(job_id, JobEvent.CANCEL_COMPLETE)
        return {"jobId": job_id, "state": self.jobs[job_id].state.value}

    async def restart_worker(self) -> dict[str, str]:
        async with self.generation_lock:
            model_id = self.active_model_id
            await self._stop_worker()
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
    ) -> None:
        async with self.generation_lock:
            if self.jobs[initial_job.id].state is JobState.CANCELLING:
                await self._finish_job(initial_job.id, JobEvent.CANCEL_COMPLETE)
                return
            conversation = self.store.get_conversation(conversation_id) or {"messages": []}
            context_messages: list[dict[str, str]] = []
            for message in conversation.get("messages", []):
                if message.get("role") in {"user", "assistant", "system"} and isinstance(
                    message.get("content"), str
                ):
                    context_messages.append(
                        {"role": message["role"], "content": message["content"]}
                    )
                if message.get("turnId") == turn_id and message.get("role") == "user":
                    break
            if self.active_model_id != initial_job.model_id or self.worker is None:
                await self._load_model(initial_job.model_id or "")
            self.active_job_id = initial_job.id
            try:
                await self._run_chat_job_serial(
                    initial_job,
                    conversation_id,
                    content,
                    max_tokens,
                    temperature,
                    image_paths,
                    context_messages,
                    turn_id,
                )
            finally:
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
    ) -> None:
        job_id = initial_job.id
        if self.jobs[job_id].state is JobState.CANCELLING:
            await self._finish_job(job_id, JobEvent.CANCEL_COMPLETE)
            return
        self.jobs[job_id] = transition_job(initial_job, JobEvent.PREPARE)
        self.store.update_job(job_id, JobState.PREPARING.value)
        await self.events.publish("job.updated", {"job_id": job_id, "state": "preparing"})
        running = transition_job(self.jobs[job_id], JobEvent.START)
        self.jobs[job_id] = running
        self.store.update_job(job_id, JobState.RUNNING.value)
        await self.events.publish("job.updated", {"job_id": job_id, "state": "running"})
        output: list[str] = []
        try:
            if self.worker is None:
                raise WorkerProtocolError("worker is unavailable")
            async for event in self.worker.generate(
                job_id, content, max_tokens, temperature, image_paths, messages
            ):
                event_type = event["type"]
                payload = event["payload"]
                if event_type == "generation.delta":
                    delta = str(payload.get("text", ""))
                    output.append(delta)
                    await self.events.publish(event_type, {"job_id": job_id, "text": delta})
                if event_type == "generation.cancelled":
                    await self._finish_job(job_id, JobEvent.CANCEL_COMPLETE)
                    return
                if event_type == "generation.failed":
                    await self._finish_job(job_id, JobEvent.FAIL, "INFERENCE_FAILED")
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
                }
            )
            await self._finish_job(job_id, JobEvent.COMPLETE)
        except Exception:
            await self._finish_job(job_id, JobEvent.FAIL, "INFERENCE_FAILED")

    async def _finish_job(
        self, job_id: str, event: JobEvent, error_code: str | None = None
    ) -> None:
        current = self.jobs[job_id]
        try:
            updated = transition_job(current, event, error_code)
        except ValueError:
            if current.state in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}:
                return
            raise
        self.jobs[job_id] = updated
        self.store.update_job(job_id, updated.state.value, updated.error_code)
        await self.events.publish(
            f"job.{updated.state.value}",
            {"job_id": job_id, "state": updated.state.value, "error_code": updated.error_code},
        )

    async def _stop_worker(self) -> None:
        if self.worker:
            await self.worker.stop()
        self.worker = None
        self.active_model_id = None

    def _forget_job_task(self, job_id: str, task: asyncio.Task[None]) -> None:
        if self.job_tasks.get(job_id) is task:
            self.job_tasks.pop(job_id, None)

    async def close(self) -> None:
        tasks = tuple(self.job_tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self._stop_worker()
        self.store.close()
