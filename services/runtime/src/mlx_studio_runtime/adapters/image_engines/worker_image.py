"""Worker-only image engine bridge and cooperative step cancellation."""

import os
import sys
import threading
import time
from collections.abc import Callable
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from mlx_studio_runtime.adapters.image_engines.fake_image import write_fake_png
from mlx_studio_runtime.domain.image_generation import ImageParameters


class WorkerImageEngine:
    def __init__(self, engine: str, model_path: str) -> None:
        self.engine = engine
        self.adapter: Any = None
        if engine != "fake":
            from mlx_studio_runtime.adapters.image_engines.mflux_image import MfluxImageEngine

            if engine != "mflux":
                raise ValueError("IMAGE_MODEL_NOT_SUPPORTED")
            with redirect_stdout(sys.stderr):
                self.adapter = MfluxImageEngine(model_path)

    def generate(
        self,
        payload: dict[str, Any],
        signals: tuple[threading.Event, threading.Event],
        emit: Callable[[str, dict[str, Any]], None],
    ) -> None:
        job_id = str(payload["job_id"])
        cancel, shutdown = signals
        cancel.clear()
        output: Path | None = None
        try:
            parameters = ImageParameters(**payload["parameters"])
            output = self._output_path(str(payload["output_path"]))
            emit("generation.started", {"job_id": job_id})

            def progress(step: int) -> None:
                if cancel.is_set() or shutdown.is_set():
                    raise InterruptedError("IMAGE_CANCELLED")
                emit("image.progress", {"job_id": job_id, "step": step, "steps": parameters.steps})

            if self.engine == "fake":
                for step in range(1, parameters.steps + 1):
                    time.sleep(0.05)
                    progress(step)
                write_fake_png(output, parameters.width, parameters.height, parameters.seed)
            else:
                with redirect_stdout(sys.stderr):
                    self.adapter.generate(parameters.to_dict(), output, progress)
            if cancel.is_set() or shutdown.is_set():
                raise InterruptedError("IMAGE_CANCELLED")
            emit("generation.completed", {"job_id": job_id})
        except Exception:  # Worker inference boundary; no prompts or upstream errors enter logs.
            if output:
                output.unlink(missing_ok=True)
            cancelled = cancel.is_set() or shutdown.is_set()
            emit(
                "generation.cancelled" if cancelled else "generation.failed",
                {
                    "job_id": job_id,
                    "error_code": "IMAGE_GENERATION_FAILED",
                },
            )

    @staticmethod
    def _output_path(value: str) -> Path:
        configured = os.getenv("MLX_STUDIO_IMAGE_OUTPUT_ROOT")
        if not configured:
            raise ValueError("IMAGE_OUTPUT_ROOT_MISSING")
        root = Path(configured).resolve()
        path = Path(value).resolve()
        if path.parent != root / ".pending" or path.suffix != ".png":
            raise ValueError("IMAGE_PATH_INVALID")
        return path
