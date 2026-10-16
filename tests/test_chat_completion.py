import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mlx_studio_runtime.adapters.persistence.sqlite_repositories import (
    SQLiteRepositories,
)
from mlx_studio_runtime.adapters.text_engines.session import EngineSession
from mlx_studio_runtime.entrypoints.http.contracts import ChatMessageRequest
from runtime_fixtures import create_test_runtime

RUNTIME_SOURCE = Path(__file__).parents[1] / "services/runtime/src"


class CompletionTests(unittest.TestCase):
    def test_default_budget_and_length_metadata(self) -> None:
        self.assertEqual(
            ChatMessageRequest(content="hello", model_id="test").max_tokens, 4096
        )
        events = []
        session = EngineSession()
        session.model_id = "test"
        session.emit = lambda kind, payload: events.append((kind, payload))

        def chunks(*_args):
            yield "partial"
            session._record_completion(
                SimpleNamespace(finish_reason="length", generation_tokens=8)
            )
            yield " tail"

        session._chunks = chunks
        session._generate({"job_id": "job", "max_tokens": 8})
        self.assertEqual(
            events[-1],
            (
                "generation.completed",
                {
                    "job_id": "job",
                    "finish_reason": "length",
                    "generation_tokens": 8,
                },
            ),
        )
        session._chunks = lambda *_args: iter(["done"])
        session._generate({"job_id": "next"})
        self.assertEqual(events[-1][1]["finish_reason"], "stop")


class CompletionPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_length_reason_reaches_events_and_survives_reload(self) -> None:
        class Worker:
            async def generate(self, job_id, *_args):
                yield {
                    "type": "generation.delta",
                    "payload": {"job_id": job_id, "text": "partial"},
                }
                yield {
                    "type": "generation.completed",
                    "payload": {
                        "job_id": job_id,
                        "finish_reason": "length",
                        "generation_tokens": 8,
                    },
                }

            async def stop(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.db"
            service = create_test_runtime(SQLiteRepositories(path), RUNTIME_SOURCE)
            service.inference.worker = Worker()  # type: ignore[assignment]
            service.inference.active_model_id = "builtin-fake-text"
            queue = await service.events.subscribe()
            conversation = await service.chat.create_conversation(
                "Test", "builtin-fake-text"
            )
            sent = await service.chat.send_message(
                conversation["id"], "hello", "builtin-fake-text", 8, 0
            )
            await service.scheduler.tasks[sent["jobId"]]
            events = []
            while not queue.empty():
                events.append(queue.get_nowait())
            terminal = next(event for event in events if event.type == "job.succeeded")
            self.assertEqual(terminal.payload["finish_reason"], "length")
            await service.close()
            reopened = SQLiteRepositories(path)
            try:
                reply = reopened.conversations.get(conversation["id"])["messages"][-1]
                self.assertEqual(reply["content"], "partial")
                self.assertEqual(reply["parameters"]["finishReason"], "length")
                self.assertEqual(reply["parameters"]["generationTokens"], 8)
            finally:
                reopened.close()
