"""Concrete text/VLM engine loading, streaming and cleanup inside the Worker."""

import gc
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import redirect_stdout
from typing import Any, cast

from mlx_studio_runtime.adapters.image_engines.worker_image import WorkerImageEngine


class EngineSession:
    def __init__(self) -> None:
        self.cancel = threading.Event()
        self.shutdown = threading.Event()
        self.model_id: str | None = None
        self.model: Any = None
        self.tokenizer: Any = None
        self.processor: Any = None
        self.model_config: Any = None
        self.engine = "fake"
        self.image_engine: WorkerImageEngine | None = None
        self.finish_reason = "stop"
        self.generation_tokens = 0

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    def _load(self, payload: dict[str, Any]) -> None:
        self._unload()
        manifest_value = payload.get("manifest", {})
        if not isinstance(manifest_value, dict):
            raise ValueError("manifest must be an object")
        manifest = cast(dict[str, object], manifest_value)
        self.model_id = str(manifest.get("id", ""))
        self.engine = str(manifest.get("engine", "fake"))
        self.emit("model.loading", {"model_id": self.model_id})
        if self.engine in {"mlx-lm", "mlx-vlm", "mflux"}:
            self._configure_mlx()
        if manifest.get("task") == "image-generation":
            self.image_engine = WorkerImageEngine(self.engine, str(manifest["localPath"]))
        elif self.engine == "mlx-lm":
            from mlx_lm import load  # type: ignore[import-not-found]

            with redirect_stdout(sys.stderr):
                self.model, self.tokenizer = load(
                    str(manifest["localPath"]),
                    trust_remote_code=False,
                )
        elif self.engine == "mlx-vlm":
            from mlx_vlm import load  # type: ignore[import-not-found]
            from mlx_vlm.utils import load_config  # type: ignore[import-not-found]

            from mlx_studio_runtime.adapters.text_engines.streaming_decoder import (
                configure_streaming_decoder,
            )

            model_path = str(manifest["localPath"])
            with redirect_stdout(sys.stderr):
                self.model, self.processor = load(model_path, trust_remote_code=False)
                configure_streaming_decoder(self.processor)
                self.model_config = load_config(model_path)
        elif self.engine != "fake":
            raise RuntimeError(f"engine is not available in this Worker: {self.engine}")
        self.emit("model.loaded", {"model_id": self.model_id, "engine": self.engine})

    def _generate(self, payload: dict[str, Any]) -> None:
        if self.model_id is None:
            raise RuntimeError("MODEL_NOT_LOADED")
        job_id = str(payload["job_id"])
        prompt = str(payload.get("prompt", ""))
        max_tokens = max(1, min(int(payload.get("max_tokens", 128)), 8192))
        temperature = max(0.0, min(float(payload.get("temperature", 0.7)), 2.0))
        self.cancel.clear()
        self.finish_reason = "stop"
        self.generation_tokens = 0
        self.emit("generation.started", {"job_id": job_id})
        try:
            for chunk in self._chunks(payload, prompt, max_tokens, temperature):
                if self.cancel.is_set() or self.shutdown.is_set():
                    self.emit("generation.cancelled", {"job_id": job_id})
                    return
                if chunk:
                    self.emit("generation.delta", {"job_id": job_id, "text": chunk})
                if self.engine == "fake":
                    time.sleep(0.015)
            terminal = "cancelled" if self.cancel.is_set() else "completed"
            self.emit(
                f"generation.{terminal}",
                {
                    "job_id": job_id,
                    "finish_reason": self.finish_reason,
                    "generation_tokens": self.generation_tokens,
                },
            )
        except Exception as error:
            if self.cancel.is_set() or self.shutdown.is_set():
                self.emit("generation.cancelled", {"job_id": job_id})
                return
            self.emit(
                "generation.failed",
                {"job_id": job_id, "error_code": "INFERENCE_FAILED", "message": str(error)},
            )

    def _chunks(
        self,
        payload: dict[str, Any],
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Iterator[str]:
        if self.engine == "mlx-lm":
            return self._mlx_chunks(prompt, max_tokens, temperature, payload.get("messages", []))
        if self.engine == "mlx-vlm":
            return self._vlm_chunks(
                prompt,
                max_tokens,
                temperature,
                payload.get("image_paths", []),
                payload.get("messages", []),
            )
        return self._fake_chunks(prompt)

    def _mlx_chunks(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        messages: object,
    ) -> Iterator[str]:
        from mlx_lm import stream_generate  # type: ignore[import-not-found]
        from mlx_lm.sample_utils import make_sampler  # type: ignore[import-not-found]

        rendered = self.tokenizer.apply_chat_template(
            normalize_messages(messages, prompt),
            tokenize=False,
            add_generation_prompt=True,
        )
        sampler = make_sampler(temp=temperature)
        for response in stream_generate(
            self.model,
            self.tokenizer,
            rendered,
            max_tokens=max_tokens,
            sampler=sampler,
        ):
            self._record_completion(response)
            if self.cancel.is_set():
                return
            yield response.text

    def _vlm_chunks(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        image_paths: object,
        messages: object = None,
    ) -> Iterator[str]:
        if not isinstance(image_paths, list) or len(image_paths) > 4:
            raise ValueError("zero to four image paths are supported")
        from mlx_vlm import stream_generate  # type: ignore[import-not-found]
        from mlx_vlm.prompt_utils import apply_chat_template  # type: ignore[import-not-found]

        paths = [str(path) for path in image_paths]
        formatted = apply_chat_template(
            self.processor,
            self.model_config,
            normalize_messages(messages, prompt),
            num_images=len(paths),
            add_generation_prompt=True,
            enable_thinking=False,
        )
        if not isinstance(formatted, str):
            raise ValueError("Chat template did not produce a text prompt")
        for response in stream_generate(
            model=self.model,
            processor=self.processor,
            prompt=formatted,
            image=paths,
            max_tokens=max_tokens,
            temperature=temperature,
            verbose=False,
        ):
            self._record_completion(response)
            if self.cancel.is_set():
                return
            text = response if isinstance(response, str) else getattr(response, "text", "")
            if text:
                yield str(text)

    def _record_completion(self, response: Any) -> None:
        reason = getattr(response, "finish_reason", None)
        if reason in {"stop", "length"}:
            self.finish_reason = reason
        tokens = getattr(response, "generation_tokens", None)
        if isinstance(tokens, int):
            self.generation_tokens = tokens

    @staticmethod
    def _fake_chunks(prompt: str) -> Iterator[str]:
        reply = (
            f"FakeEngine received: {prompt.strip()}\n"
            "This response is streamed for UI and protocol development."
        )
        for start in range(0, len(reply), 5):
            yield reply[start : start + 5]

    def _unload(self) -> None:
        release_mlx = self.engine in {"mlx-lm", "mlx-vlm", "mflux"} and (
            self.model is not None or self.image_engine is not None
        )
        self.model = None
        self.tokenizer = None
        self.processor = None
        self.model_config = None
        self.model_id = None
        self.image_engine = None
        self.engine = "fake"
        if release_mlx:
            import mlx.core as mx  # type: ignore[import-not-found]

            mx.synchronize()
            gc.collect()
            mx.clear_cache()

    @staticmethod
    def _configure_mlx() -> None:
        import mlx.core as mx  # type: ignore[import-not-found]

        # MLX 0.32.1's compiled-cache teardown can segfault after Qwen inference.
        mx.disable_compile()
        mx.set_cache_limit(4 * 1024**3)


def normalize_messages(messages: object, prompt: str) -> list[dict[str, str]]:
    if not isinstance(messages, list):
        return [{"role": "user", "content": prompt}]
    normalized: list[dict[str, str]] = []
    for value in messages:
        if not isinstance(value, dict):
            return [{"role": "user", "content": prompt}]
        message = cast(dict[str, object], value)
        role = message.get("role")
        content = message.get("content")
        if (
            not isinstance(role, str)
            or role
            not in {
                "user",
                "assistant",
                "system",
            }
            or not isinstance(content, str)
        ):
            return [{"role": "user", "content": prompt}]
        normalized.append({"role": role, "content": content})
    return normalized or [{"role": "user", "content": prompt}]
