"""Chat submissions and result persistence; no transport or Worker construction."""

import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from mlx_studio_runtime.application.chat_support import (
    conversation_context,
    validate_attachments,
)
from mlx_studio_runtime.application.ports import (
    ConversationRepository,
    InferenceSession,
    JobAdmission,
    SubmissionJournal,
)
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.domain.jobs import Job, JobEvent, JobState
from mlx_studio_runtime.domain.models import ModelManifest


class ChatService:
    def __init__(
        self,
        conversations: ConversationRepository,
        attachment_paths: Callable[[list[str]], list[str]],
        models: dict[str, ModelManifest],
        scheduler: JobAdmission,
        runtime: InferenceSession,
        journal: SubmissionJournal,
    ) -> None:
        self.conversations = conversations
        self.attachment_paths = attachment_paths
        self.models = models
        self.scheduler = scheduler
        self.runtime = runtime
        self.job_lifecycle = scheduler.lifecycle
        self.jobs = scheduler.lifecycle.items
        self.events = runtime.events
        self.journal = journal

    async def create_conversation(self, title: str, model_id: str | None) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "title": title,
            "modelId": model_id,
            "parameters": {},
        }
        self.conversations.save(item)
        return self.conversations.get(item["id"]) or item

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
        client_request_id: str | None = None,
    ) -> dict[str, str]:
        digest = hashlib.sha256(
            json.dumps(
                {
                    "content": content,
                    "model": model_id,
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                    "attachments": attachment_ids or [],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if client_request_id:
            previous = self.journal.find(conversation_id, client_request_id)
            if previous:
                if previous[0] != digest:
                    raise RuntimeFault(
                        RuntimeErrorInfo("IDEMPOTENCY_CONFLICT", "请求编号已用于不同输入")
                    )
                return {"jobId": previous[1], "state": "accepted"}
        self.scheduler.check_admission(model_id)
        conversation = self.conversations.get(conversation_id)
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
        image_paths = self.attachment_paths(attachment_ids)
        turn_id = turn_id or str(uuid.uuid4())
        job = Job(str(uuid.uuid4()), "chat", JobState.QUEUED, model_id)

        def persist_submission() -> None:
            if persist_user_message:
                self.conversations.save_message(
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
            if client_request_id:
                self.journal.save(conversation_id, client_request_id, digest, job.id)

        await self.job_lifecycle.register(
            job,
            {
                "conversationId": conversation_id,
                "maxTokens": max_tokens,
                "temperature": temperature,
                "attachmentIds": attachment_ids,
                "turnId": turn_id,
                "replaceAssistantMessageId": replace_assistant_message_id,
            },
            persist=persist_submission,
        )
        self.scheduler.schedule(
            job,
            lambda: self._run_chat_job_serial(
                job,
                conversation_id,
                content,
                max_tokens,
                temperature,
                image_paths,
                conversation_context(self.conversations, conversation_id, turn_id),
                turn_id,
                replace_assistant_message_id,
            ),
        )
        return {"jobId": job.id, "state": job.state.value}

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
        await self.job_lifecycle.transition(job_id, JobEvent.START)
        if self.runtime.worker is None:
            raise RuntimeError("worker is unavailable")
        result = await self._collect_reply(
            job_id,
            self.runtime.worker.generate(
                job_id, content, max_tokens, temperature, image_paths, messages
            ),
        )
        if result is None:
            return
        output, completion = result

        def persist_result() -> None:
            self.conversations.save_message(
                {
                    "id": str(uuid.uuid4()),
                    "turnId": turn_id,
                    "conversationId": conversation_id,
                    "role": "assistant",
                    "content": output,
                    "modelSnapshot": self.models[initial_job.model_id or ""].to_dict(),
                    "parameters": {
                        "maxTokens": max_tokens,
                        "temperature": temperature,
                        "finishReason": completion.get("finish_reason", "stop"),
                        "generationTokens": completion.get("generation_tokens"),
                    },
                },
                replace_message_id=replace_assistant_message_id,
            )

        await self.job_lifecycle.finish(
            job_id,
            JobEvent.COMPLETE,
            persist=persist_result,
            finish_reason=str(completion.get("finish_reason", "stop")),
        )

    async def _collect_reply(
        self, job_id: str, events: AsyncIterator[dict[str, Any]]
    ) -> tuple[str, dict[str, Any]] | None:
        output: list[str] = []
        completion: dict[str, Any] | None = None
        async for event in events:
            event_type, payload = event["type"], event["payload"]
            if event_type == "generation.delta":
                delta = str(payload.get("text", ""))
                output.append(delta)
                self.job_lifecycle.append_output(job_id, delta)
                await self.events.publish(event_type, {"job_id": job_id, "text": delta})
            elif event_type == "generation.completed":
                completion = payload
            elif event_type == "generation.cancelled":
                await self.job_lifecycle.finish(job_id, JobEvent.CANCEL_COMPLETE)
                return None
            elif event_type == "generation.failed":
                code = str(payload.get("error_code", "INFERENCE_FAILED"))
                raise RuntimeFault(RuntimeErrorInfo(code, "模型推理失败", True))
        if self.jobs[job_id].state is JobState.CANCELLING:
            await self.job_lifecycle.finish(job_id, JobEvent.CANCEL_COMPLETE)
            return None
        if completion is None:
            raise RuntimeError("WORKER_ENDED_EARLY")
        return "".join(output), completion

    async def regenerate(
        self, conversation_id: str, model_id: str, max_tokens: int | None = None
    ) -> dict[str, str]:
        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            raise RuntimeFault(RuntimeErrorInfo("CONVERSATION_NOT_FOUND", "找不到此会话"))
        messages = conversation.get("messages", [])
        user = next((item for item in reversed(messages) if item["role"] == "user"), None)
        if user is None:
            raise RuntimeFault(RuntimeErrorInfo("MESSAGE_NOT_FOUND", "没有可重新生成的用户消息"))
        turn_id = str(user.get("turnId") or user["id"])
        assistant = next(
            (
                item
                for item in reversed(messages)
                if item["role"] == "assistant" and item.get("turnId") == turn_id
            ),
            None,
        )
        parameters = user.get("parameters", {})
        return await self.send_message(
            conversation_id,
            str(user["content"]),
            model_id,
            max_tokens if max_tokens is not None else int(parameters.get("maxTokens", 4096)),
            float(parameters.get("temperature", 0.7)),
            [str(item["id"]) for item in user.get("attachments", [])],
            persist_user_message=False,
            turn_id=turn_id,
            replace_assistant_message_id=str(assistant["id"]) if assistant else None,
        )
