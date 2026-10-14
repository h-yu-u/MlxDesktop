"""NDJSON Worker used by the Supervisor. stdout is reserved for protocol frames."""

import gc
import json
import logging
import queue
import sys
import threading
import time
import traceback
import uuid
from collections.abc import Iterator
from contextlib import redirect_stdout
from typing import Any, cast

from mlx_studio_runtime import PROTOCOL_VERSION
from mlx_studio_runtime.adapters.image_engines.worker_image import WorkerImageEngine

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
LOGGER = logging.getLogger("mlx_studio.worker")


class Worker:
    def __init__(self) -> None:
        self.commands: queue.Queue[dict[str, Any]] = queue.Queue()
        self.cancel = threading.Event()
        self.shutdown = threading.Event()
        self.sequence = 0
        self.model_id: str | None = None
        self.model: Any = None
        self.tokenizer: Any = None
        self.processor: Any = None
        self.model_config: Any = None
        self.engine = "fake"
        self.image_engine: WorkerImageEngine | None = None
        self.protocol_output = sys.stdout

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.sequence += 1
        frame = {
            "protocol_version": PROTOCOL_VERSION,
            "seq": self.sequence,
            "type": event_type,
            "payload": payload,
        }
        self.protocol_output.write(
            json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        self.protocol_output.flush()

    def read_commands(self) -> None:
        for line in sys.stdin:
            try:
                command = json.loads(line)
                self._validate_command(command)
            except (json.JSONDecodeError, ValueError) as error:
                LOGGER.error("Invalid worker protocol frame: %s", error)
                self.emit("worker.protocol_error", {"message": str(error)})
                self.shutdown.set()
                return
            if command["type"] == "generation.cancel":
                self.cancel.set()
            if command["type"] == "worker.shutdown":
                self.shutdown.set()
            self.commands.put(command)

    @staticmethod
    def _validate_command(command: object) -> None:
        if not isinstance(command, dict):
            raise ValueError("command must be an object")
        if command.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError("protocol_version mismatch")
        if not isinstance(command.get("id"), str) or not isinstance(command.get("type"), str):
            raise ValueError("command id and type are required")
        if not isinstance(command.get("payload", {}), dict):
            raise ValueError("payload must be an object")

    def run(self) -> int:
        self.emit("worker.ready", {"worker_id": str(uuid.uuid4())})
        threading.Thread(target=self.read_commands, daemon=True).start()
        while not self.shutdown.is_set():
            try:
                command = self.commands.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self.handle(command)
            except Exception as error:  # Worker process boundary.
                LOGGER.error("Worker command failed: %s\n%s", error, traceback.format_exc())
                self.emit(
                    "worker.command_failed",
                    {"command_id": command["id"], "error": type(error).__name__},
                )
        self._unload()
        self.emit("worker.stopped", {})
        return 0

    def handle(self, command: dict[str, Any]) -> None:
        kind = command["type"]
        payload = command.get("payload", {})
        if kind == "worker.load":
            self._load(payload)
        elif kind == "image.start":
            if self.image_engine is None:
                raise RuntimeError("IMAGE_MODEL_NOT_LOADED")
            self.image_engine.generate(payload, (self.cancel, self.shutdown), self.emit)
        elif kind == "generation.start":
            self._generate(payload)
        elif kind == "generation.cancel":
            return
        elif kind == "worker.shutdown":
            self.shutdown.set()
        elif kind == "worker.unload":
            self._unload()
        else:
            raise ValueError(f"unsupported command type: {kind}")

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

            model_path = str(manifest["localPath"])
            with redirect_stdout(sys.stderr):
                self.model, self.processor = load(model_path, trust_remote_code=False)
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
            self.emit(f"generation.{terminal}", {"job_id": job_id})
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
            if self.cancel.is_set():
                return
            text = response if isinstance(response, str) else getattr(response, "text", "")
            if text:
                yield str(text)

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
        if not isinstance(role, str) or role not in {
            "user",
            "assistant",
            "system",
        } or not isinstance(content, str):
            return [{"role": "user", "content": prompt}]
        normalized.append({"role": role, "content": content})
    return normalized or [{"role": "user", "content": prompt}]


def main() -> int:
    return Worker().run()


if __name__ == "__main__":
    raise SystemExit(main())
