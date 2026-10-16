"""NDJSON Worker used by the Supervisor. stdout is reserved for protocol frames."""

import json
import logging
import queue
import sys
import threading
import uuid
from typing import Any

from mlx_studio_runtime import PROTOCOL_VERSION
from mlx_studio_runtime.adapters.import_diagnostics import import_failure_chain
from mlx_studio_runtime.adapters.text_engines.session import EngineSession

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
LOGGER = logging.getLogger("mlx_studio.worker")


class Worker(EngineSession):
    def __init__(self) -> None:
        self.commands: queue.Queue[dict[str, Any]] = queue.Queue()
        super().__init__()
        self.sequence = 0
        self.protocol_lock = threading.Lock()
        self.protocol_output = sys.stdout

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        with self.protocol_lock:
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
        # The Supervisor can exit without a shutdown command (for example after a crash).
        self.shutdown.set()

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
                if isinstance(error, ImportError):
                    LOGGER.error("Worker import failed: %s", import_failure_chain(error))
                else:
                    LOGGER.error("Worker command failed: %s", type(error).__name__)
                self.emit(
                    "worker.command_failed",
                    {
                        "command_id": command["id"],
                        "job_id": command.get("payload", {}).get("job_id"),
                        "error": type(error).__name__,
                    },
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
        elif kind == "inference.start":
            from mlx_studio_runtime.adapters.text_engines.structured import generate_structured

            generate_structured(self, payload)
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


def main() -> int:
    return Worker().run()


if __name__ == "__main__":
    raise SystemExit(main())
