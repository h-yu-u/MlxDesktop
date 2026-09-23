"""NDJSON Worker used by the Supervisor. stdout is reserved for protocol frames."""

import json
import logging
import queue
import sys
import threading
import time
import traceback
import uuid
from collections.abc import Iterator
from typing import Any

from mlx_studio_runtime import PROTOCOL_VERSION

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

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.sequence += 1
        frame = {
            "protocol_version": PROTOCOL_VERSION,
            "seq": self.sequence,
            "type": event_type,
            "payload": payload,
        }
        sys.stdout.write(json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()

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
        payload = command.get("payload", {})
        if not isinstance(payload, dict):
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
        manifest = payload.get("manifest", {})
        self.model_id = str(manifest.get("id", ""))
        self.engine = str(manifest.get("engine", "fake"))
        self.emit("model.loading", {"model_id": self.model_id})
        if self.engine == "mlx-lm":
            from mlx_lm import load  # type: ignore[import-not-found]

            self.model, self.tokenizer = load(str(manifest["localPath"]), trust_remote_code=False)
        elif self.engine == "mlx-vlm":
            from mlx_vlm import load  # type: ignore[import-not-found]
            from mlx_vlm.utils import load_config  # type: ignore[import-not-found]

            model_path = str(manifest["localPath"])
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
            if self.engine == "mlx-lm":
                chunks = self._mlx_chunks(
                    prompt, max_tokens, temperature, payload.get("messages", [])
                )
            elif self.engine == "mlx-vlm":
                chunks = self._vlm_chunks(
                    prompt, max_tokens, temperature, payload.get("image_paths", [])
                )
            else:
                chunks = self._fake_chunks(prompt)
            for chunk in chunks:
                if self.cancel.is_set() or self.shutdown.is_set():
                    self.emit("generation.cancelled", {"job_id": job_id})
                    return
                if chunk:
                    self.emit("generation.delta", {"job_id": job_id, "text": chunk})
                if self.engine == "fake":
                    time.sleep(0.015)
            state = "cancelled" if self.cancel.is_set() else "completed"
            self.emit(f"generation.{state}", {"job_id": job_id})
        except Exception as error:
            self.emit(
                "generation.failed",
                {"job_id": job_id, "error_code": "INFERENCE_FAILED", "message": str(error)},
            )

    def _mlx_chunks(
        self, prompt: str, max_tokens: int, temperature: float, messages: object
    ) -> Iterator[str]:
        from mlx_lm import stream_generate  # type: ignore[import-not-found]

        chat_messages = (
            messages
            if isinstance(messages, list)
            and all(
                isinstance(message, dict)
                and message.get("role") in {"user", "assistant", "system"}
                and isinstance(message.get("content"), str)
                for message in messages
            )
            else [{"role": "user", "content": prompt}]
        )
        prompt = self.tokenizer.apply_chat_template(
            chat_messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        yield from (
            response.text
            for response in stream_generate(
                self.model, self.tokenizer, prompt, max_tokens=max_tokens, temp=temperature
            )
        )

    def _vlm_chunks(
        self, prompt: str, max_tokens: int, temperature: float, image_paths: object
    ) -> Iterator[str]:
        if not isinstance(image_paths, list) or len(image_paths) > 4:
            raise ValueError("one to four image paths are supported")
        from mlx_vlm import generate  # type: ignore[import-not-found]
        from mlx_vlm.prompt_utils import apply_chat_template  # type: ignore[import-not-found]

        paths = [str(path) for path in image_paths]
        formatted = apply_chat_template(
            self.processor,
            self.model_config,
            prompt,
            num_images=len(paths),
            add_generation_prompt=True,
        )
        result = generate(
            model=self.model,
            processor=self.processor,
            prompt=formatted,
            image=paths,
            max_tokens=max_tokens,
            temperature=temperature,
            verbose=False,
        )
        text = result if isinstance(result, str) else getattr(result, "text", str(result))
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
        self.model = None
        self.tokenizer = None
        self.processor = None
        self.model_config = None
        self.model_id = None


def main() -> int:
    return Worker().run()


if __name__ == "__main__":
    raise SystemExit(main())
