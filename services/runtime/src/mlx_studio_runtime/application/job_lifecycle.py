"""Job state transitions with persistence and event publication."""

from mlx_studio_runtime.adapters.event_hub import EventHub
from mlx_studio_runtime.adapters.persistence.sqlite_store import SQLiteStore
from mlx_studio_runtime.domain.jobs import (
    Job,
    JobEvent,
    JobState,
    terminal_state,
    transition_job,
)


class JobLifecycle:
    def __init__(self, store: SQLiteStore, events: EventHub) -> None:
        self.store = store
        self.events = events
        self.items: dict[str, Job] = {}

    async def register(self, job: Job, request: dict[str, object]) -> None:
        self.items[job.id] = job
        self.store.save_job(
            {
                "id": job.id,
                "kind": job.kind,
                "state": job.state.value,
                "modelId": job.model_id,
                "request": request,
            }
        )
        await self.events.publish(
            "job.updated",
            {"job_id": job.id, "state": job.state.value},
        )

    async def transition(self, job_id: str, event: JobEvent) -> Job:
        updated = transition_job(self.items[job_id], event)
        self.items[job_id] = updated
        self.store.update_job(job_id, updated.state.value)
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
    ) -> Job:
        current = self.items[job_id]
        if terminal_state(current.state):
            return current
        updated = transition_job(current, event, error_code)
        self.items[job_id] = updated
        self.store.update_job(job_id, updated.state.value, updated.error_code)
        await self.events.publish(
            f"job.{updated.state.value}",
            {
                "job_id": job_id,
                "state": updated.state.value,
                "error_code": updated.error_code,
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
