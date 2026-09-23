"""Supervisor-side lifecycle and NDJSON transport for one Worker subprocess."""

import asyncio
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from mlx_studio_runtime import PROTOCOL_VERSION


class WorkerProtocolError(RuntimeError):
    pass


class WorkerHost:
    def __init__(self, runtime_source: Path) -> None:
        self.runtime_source = runtime_source
        self.process: asyncio.subprocess.Process | None = None
        self.write_lock = asyncio.Lock()
        self.reader_task: asyncio.Task[None] | None = None
        self.last_sequence = 0

    async def start(self) -> None:
        if self.process and self.process.returncode is None:
            return
        env = os.environ.copy()
        env.pop("MLX_STUDIO_SESSION_TOKEN", None)
        env.pop("MLX_STUDIO_EXTERNAL_API_TOKEN", None)
        current = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{self.runtime_source}{os.pathsep}{current}".rstrip(os.pathsep)
        command = (
            [sys.executable, "--worker"]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "mlx_studio_runtime.entrypoints.worker.main"]
        )
        self.process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self.last_sequence = 0
        self.reader_task = asyncio.create_task(self._drain_stderr())
        event = await asyncio.wait_for(self._read_event(), timeout=10)
        if event["type"] != "worker.ready":
            raise WorkerProtocolError("worker failed readiness handshake")

    async def load(self, manifest: dict[str, Any]) -> None:
        await self.start()
        await self._send("worker.load", {"manifest": manifest})
        await self._wait_for("model.loaded")

    async def generate(
        self,
        job_id: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        image_paths: list[str] | None = None,
        messages: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        await self._send(
            "generation.start",
            {
                "job_id": job_id,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "image_paths": image_paths or [],
                "messages": messages or [],
            },
        )
        async for event in self._events_until_terminal(job_id):
            yield event

    async def cancel(self, job_id: str) -> None:
        await self._send("generation.cancel", {"job_id": job_id})

    async def stop(self) -> None:
        if self.process is None:
            return
        if self.process.returncode is None:
            try:
                await self._send("worker.shutdown", {})
                await asyncio.wait_for(self.process.wait(), timeout=3)
            except (TimeoutError, BrokenPipeError, WorkerProtocolError):
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2)
                except TimeoutError:
                    self.process.kill()
                    await self.process.wait()
        if self.reader_task:
            await self.reader_task
        self.process = None

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def _send(self, command_type: str, payload: dict[str, Any]) -> None:
        if (
            self.process is None
            or self.process.stdin is None
            or self.process.returncode is not None
        ):
            raise WorkerProtocolError("worker is not running")
        frame = {
            "protocol_version": PROTOCOL_VERSION,
            "id": str(uuid.uuid4()),
            "type": command_type,
            "payload": payload,
        }
        async with self.write_lock:
            self.process.stdin.write((json.dumps(frame) + "\n").encode())
            await self.process.stdin.drain()

    async def _read_event(self) -> dict[str, Any]:
        if self.process is None or self.process.stdout is None:
            raise WorkerProtocolError("worker stdout is unavailable")
        line = await self.process.stdout.readline()
        if not line:
            raise WorkerProtocolError("worker exited without an event")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise WorkerProtocolError("worker emitted invalid JSON") from error
        if event.get("protocol_version") != PROTOCOL_VERSION:
            raise WorkerProtocolError("worker protocol version mismatch")
        if event.get("seq") != self.last_sequence + 1:
            raise WorkerProtocolError("worker event sequence is not monotonic")
        if not isinstance(event.get("payload"), dict) or not isinstance(event.get("type"), str):
            raise WorkerProtocolError("worker event schema is invalid")
        self.last_sequence = event["seq"]
        return event

    async def _wait_for(self, event_type: str) -> dict[str, Any]:
        while True:
            event = await asyncio.wait_for(self._read_event(), timeout=120)
            if event["type"] == "worker.command_failed":
                raise WorkerProtocolError("worker command failed")
            if event["type"] == event_type:
                return event

    async def _events_until_terminal(self, job_id: str) -> AsyncIterator[dict[str, Any]]:
        terminal = {"generation.completed", "generation.cancelled", "generation.failed"}
        while True:
            event = await self._read_event()
            payload = event["payload"]
            if payload.get("job_id") not in {None, job_id}:
                raise WorkerProtocolError("Worker returned an event for another job")
            yield event
            if event["type"] in terminal:
                return

    async def _drain_stderr(self) -> None:
        if self.process is None or self.process.stderr is None:
            return
        while line := await self.process.stderr.readline():
            text = line.decode(errors="replace").rstrip()
            if text:
                print(f"[worker] {text}", file=sys.stderr)
