"""Job state transitions with persistence and event publication."""

from collections.abc import Callable

from mlx_studio_runtime.application.ports import EventPublisher, JobRepository, Transaction
from mlx_studio_runtime.domain.jobs import (
    Job,
    JobEvent,
    JobState,
    terminal_state,
    transition_job,
)


class JobLifecycle:
    def __init__(
        self, store: JobRepository, events: EventPublisher, transaction: Transaction
    ) -> None:
        self.store = store
        self.events = events
        self.transaction = transaction
        self.items: dict[str, Job] = {}
        self.output: dict[str, str] = {}

    async def register(
        self, job: Job, request: dict[str, object], persist: Callable[[], None] | None = None
    ) -> None:
        with self.transaction():
            if persist:
                persist()
            self.store.save(
                {
                    "id": job.id,
                    "kind": job.kind,
                    "state": job.state.value,
                    "modelId": job.model_id,
                    "request": request,
                }
            )
        self.items[job.id] = job
        await self.events.publish(
            "job.updated",
            {"job_id": job.id, "state": job.state.value},
        )

    async def transition(self, job_id: str, event: JobEvent) -> Job:
        updated = transition_job(self.items[job_id], event)
        self.store.update(job_id, updated.state.value)
        self.items[job_id] = updated
        await self.events.publish(
            "job.updated",
            {"job_id": job_id, "state": updated.state.value},
        )
        return updated

    async def finish(
        self,
        job_id: str,
        event: JobEvent,
        error_code: str | None = None,
        persist: Callable[[], None] | None = None,
        finish_reason: str | None = None,
    ) -> Job:
        current = self.items[job_id]
        if terminal_state(current.state):
            return current
        updated = transition_job(current, event, error_code)
        with self.transaction():
            if persist:
                persist()
            self.store.update(job_id, updated.state.value, updated.error_code)
        self.items[job_id] = updated
        await self.events.publish(
            f"job.{updated.state.value}",
            {
                "job_id": job_id,
                "state": updated.state.value,
                "error_code": updated.error_code,
                **({"finish_reason": finish_reason} if finish_reason else {}),
            },
        )
        return updated

    async def finish_failed_or_cancelled(self, job_id: str, error_code: str) -> Job:
        current = self.items[job_id]
        if terminal_state(current.state):
            return current
        if current.state is JobState.CANCELLING:
            return await self.finish(job_id, JobEvent.CANCEL_COMPLETE)
        return await self.finish(job_id, JobEvent.FAIL, error_code)

    def append_output(self, job_id: str, text: str) -> None:
        self.output[job_id] = self.output.get(job_id, "") + text
