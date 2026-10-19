"""Scoped local provider endpoints; no ordinary Chat conversation is created."""

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import StreamingResponse

from mlx_studio_runtime.composition_root import RuntimeApplication
from mlx_studio_runtime.entrypoints.http.inference_contracts import InferenceRequest


def register_inference_routes(
    app: FastAPI, service: RuntimeApplication, authenticate: Callable[..., Awaitable[None]]
) -> None:
    async def inference_auth(
        request: Request, authorization: str | None = Header(default=None)
    ) -> None:
        scoped = service.capability_grants.authorized(authorization)
        request.state.capability_scoped = scoped
        if not scoped and not service.coding.authorized(authorization):
            await authenticate(authorization)

    @app.get("/internal/v1/inference/models", dependencies=[Depends(inference_auth)])
    async def models() -> dict[str, object]:
        return {
            "object": "list",
            "data": [
                {"id": model.id, "object": "model"}
                for model in service.catalog.models.values()
                if model.task != "image-generation"
            ],
        }

    @app.post("/internal/v1/inference/chat/completions", dependencies=[Depends(inference_auth)])
    async def complete(body: InferenceRequest, request: Request) -> Any:
        payload = body.model_dump(exclude_none=True)
        for message in payload["messages"]:
            if isinstance(message.get("content"), list):
                message["content"] = "\n".join(block["text"] for block in message["content"])
        authorization = request.headers.get("authorization")
        task = asyncio.create_task(
            service.capability_grants.complete(authorization, payload)
            if authorization and request.state.capability_scoped
            else service.provider_inference.complete(payload)
        )
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=0.2)
                if await request.is_disconnected():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    return {}
            result = await task
        except asyncio.CancelledError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
        if body.tool_choice == "none" and result["message"].get("tool_calls"):
            from fastapi import HTTPException

            raise HTTPException(400, "TOOL_CHOICE_VIOLATION")
        identity = {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.model,
        }
        if not body.stream:
            return {
                **identity,
                "choices": [
                    {
                        "index": 0,
                        "message": result["message"],
                        "finish_reason": result["finish_reason"],
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": result.get("generation_tokens", 0),
                    "total_tokens": result.get("generation_tokens", 0),
                },
            }

        async def chunks():
            message = result["message"]
            delta: dict[str, object] = {
                "role": "assistant",
                "content": message.get("content") or "",
            }
            if message.get("tool_calls"):
                delta["tool_calls"] = [
                    {"index": index, **call} for index, call in enumerate(message["tool_calls"])
                ]
            for value, reason in ((delta, None), ({}, result["finish_reason"])):
                yield (
                    "data: "
                    + json.dumps(
                        {
                            **identity,
                            "object": "chat.completion.chunk",
                            "choices": [{"index": 0, "delta": value, "finish_reason": reason}],
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
            yield "data: [DONE]\n\n"

        return StreamingResponse(chunks(), media_type="text/event-stream")
