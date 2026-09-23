import asyncio
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

RUNTIME_SOURCE = Path(__file__).parents[1] / "services" / "runtime" / "src"
sys.path.insert(0, str(RUNTIME_SOURCE))

from mlx_studio_runtime.adapters.worker_host import WorkerHost
from mlx_studio_runtime.domain.models import fake_text_manifest
from mlx_studio_runtime.entrypoints.worker.main import Worker


class WorkerHostTests(unittest.TestCase):
    def test_text_prompt_includes_persisted_conversation_history(self) -> None:
        worker = Worker()
        captured: list[dict[str, str]] = []

        class FakeTokenizer:
            def apply_chat_template(self, messages, **_kwargs):
                captured.extend(messages)
                return "rendered prompt"

        worker.tokenizer = FakeTokenizer()
        worker.model = object()
        fake_library = ModuleType("mlx_lm")
        fake_library.stream_generate = lambda *_args, **_kwargs: iter(
            [SimpleNamespace(text="answer")]
        )
        messages = [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
            {"role": "user", "content": "follow-up"},
        ]
        with patch.dict(sys.modules, {"mlx_lm": fake_library}):
            chunks = list(worker._mlx_chunks("follow-up", 16, 0.2, messages))

        self.assertEqual(
            [message["content"] for message in captured],
            ["first question", "first answer", "follow-up"],
        )
        self.assertEqual(chunks, ["answer"])

    def test_fake_worker_load_stream_cancel_and_restart(self) -> None:
        asyncio.run(self._exercise_worker())

    async def _exercise_worker(self) -> None:
        host = WorkerHost(RUNTIME_SOURCE)
        manifest = fake_text_manifest().to_dict()
        await host.load(manifest)
        stream = host.generate("job-1", "stream me", 100, 0.5)
        first = await anext(stream)
        self.assertEqual(first["type"], "generation.started")
        await host.cancel("job-1")
        remaining = [event async for event in stream]
        self.assertEqual(remaining[-1]["type"], "generation.cancelled")

        await host.stop()
        await host.start()
        await host.load(manifest)
        events = [event async for event in host.generate("job-2", "hello", 20, 0.0)]
        self.assertEqual(events[-1]["type"], "generation.completed")
        self.assertTrue(any(event["type"] == "generation.delta" for event in events))
        await host.stop()

    def test_repeated_worker_start_and_stop_is_idempotent(self) -> None:
        asyncio.run(self._exercise_repeated_worker_lifecycle())

    async def _exercise_repeated_worker_lifecycle(self) -> None:
        manifest = fake_text_manifest().to_dict()
        for cycle in range(10):
            host = WorkerHost(RUNTIME_SOURCE)
            await host.load(manifest)
            events = [
                event async for event in host.generate(f"job-{cycle}", "cycle", 16, 0.0)
            ]
            self.assertEqual(events[-1]["type"], "generation.completed")
            process = host.process
            self.assertIsNotNone(process)
            await host.stop()
            self.assertEqual(process.returncode, 0)
            self.assertIsNone(host.process)


if __name__ == "__main__":
    unittest.main()
