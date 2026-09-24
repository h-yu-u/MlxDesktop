import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

RUNTIME_SOURCE = Path(__file__).parents[1] / "services" / "runtime" / "src"
sys.path.insert(0, str(RUNTIME_SOURCE))

from mlx_studio_runtime.adapters.persistence.sqlite_store import SQLiteStore
from mlx_studio_runtime.application.runtime_service import RuntimeService
from mlx_studio_runtime.domain.jobs import Job, JobState


class RuntimeServiceTests(unittest.TestCase):
    def test_model_load_failure_always_finishes_job(self) -> None:
        asyncio.run(self._model_load_failure_always_finishes_job())

    async def _model_load_failure_always_finishes_job(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "app.db")
            service = RuntimeService(store, RUNTIME_SOURCE)
            conversation = await service.create_conversation("Test", "builtin-fake-text")
            with patch(
                "mlx_studio_runtime.application.runtime_service.WorkerHost.load",
                new=AsyncMock(side_effect=RuntimeError("load failed")),
            ):
                result = await service.send_message(
                    conversation["id"],
                    "hello",
                    "builtin-fake-text",
                    16,
                    0.0,
                )
                await service.job_tasks[result["jobId"]]
            job = service.jobs[result["jobId"]]
            self.assertEqual(job.state, JobState.FAILED)
            self.assertEqual(job.error_code, "MODEL_LOAD_FAILED")
            persisted = next(
                item for item in service.store.list_jobs() if item["id"] == result["jobId"]
            )
            self.assertEqual(persisted["state"], "failed")
            self.assertEqual(persisted["errorCode"], "MODEL_LOAD_FAILED")
            await service.close()

    def test_cancel_wins_over_late_worker_completion(self) -> None:
        asyncio.run(self._cancel_wins_over_late_worker_completion())

    async def _cancel_wins_over_late_worker_completion(self) -> None:
        class RaceWorker:
            def __init__(self) -> None:
                self.released = asyncio.Event()

            async def generate(self, *_args, **_kwargs):
                await self.released.wait()
                yield {"type": "generation.completed", "payload": {"job_id": _args[0]}}

            async def cancel(self, _job_id: str) -> None:
                self.released.set()

            async def stop(self) -> None:
                self.released.set()

        with tempfile.TemporaryDirectory() as directory:
            service = RuntimeService(SQLiteStore(Path(directory) / "app.db"), RUNTIME_SOURCE)
            conversation = await service.create_conversation("Test", "builtin-fake-text")
            worker = RaceWorker()
            service.worker = worker  # type: ignore[assignment]
            service.active_model_id = "builtin-fake-text"
            result = await service.send_message(
                conversation["id"], "cancel me", "builtin-fake-text", 16, 0.0
            )
            for _ in range(100):
                if service.active_job_id == result["jobId"]:
                    break
                await asyncio.sleep(0.001)
            cancelled = await service.cancel_job(result["jobId"])
            self.assertEqual(cancelled["state"], "cancelled")
            messages = service.store.get_conversation(conversation["id"])["messages"]
            self.assertEqual([message["role"] for message in messages], ["user"])
            await service.close()

    def test_cancelling_terminal_job_is_idempotent(self) -> None:
        asyncio.run(self._cancelling_terminal_job_is_idempotent())

    async def _cancelling_terminal_job_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = RuntimeService(SQLiteStore(Path(directory) / "app.db"), RUNTIME_SOURCE)
            service.jobs["done"] = Job("done", "chat", JobState.SUCCEEDED)
            first = await service.cancel_job("done")
            second = await service.cancel_job("done")
            self.assertEqual(first, {"jobId": "done", "state": "succeeded"})
            self.assertEqual(second, first)
            await service.close()


if __name__ == "__main__":
    unittest.main()
