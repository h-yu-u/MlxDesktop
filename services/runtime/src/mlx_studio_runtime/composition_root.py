"""Construct concrete adapters once; feature use cases receive narrow dependencies."""

import time
from pathlib import Path

from mlx_studio_runtime.adapters.agent_host import AgentHost
from mlx_studio_runtime.adapters.attachment_files import AttachmentFiles
from mlx_studio_runtime.adapters.audio_files import AudioFiles
from mlx_studio_runtime.adapters.coding_model_identity import coding_model_identity
from mlx_studio_runtime.adapters.diagnostics import HostDiagnostics
from mlx_studio_runtime.adapters.event_hub import EventHub
from mlx_studio_runtime.adapters.image_files import ImageFiles
from mlx_studio_runtime.adapters.managed_models import ManagedModelFiles
from mlx_studio_runtime.adapters.media_recovery import recover_media
from mlx_studio_runtime.adapters.model_download import download_model
from mlx_studio_runtime.adapters.model_scan import manifest_from_directory
from mlx_studio_runtime.adapters.persistence.sqlite_repositories import SQLiteRepositories
from mlx_studio_runtime.adapters.persistence.submission_journal import SubmissionJournal
from mlx_studio_runtime.adapters.worker_host import WorkerHost
from mlx_studio_runtime.application.attachments import Attachments
from mlx_studio_runtime.application.chat_service import ChatService
from mlx_studio_runtime.application.coding_gateway import CodingGateway
from mlx_studio_runtime.application.downloads import Downloads
from mlx_studio_runtime.application.image_generation_service import ImageGenerationService
from mlx_studio_runtime.application.inference_service import InferenceService
from mlx_studio_runtime.application.job_lifecycle import JobLifecycle
from mlx_studio_runtime.application.job_scheduler import JobScheduler
from mlx_studio_runtime.application.model_catalog import ModelCatalog
from mlx_studio_runtime.application.model_removal import ModelRemovalPorts, RemoveModel
from mlx_studio_runtime.application.model_runtime import ModelRuntime
from mlx_studio_runtime.application.queries import Queries
from mlx_studio_runtime.application.runtime_control import RuntimeControl
from mlx_studio_runtime.application.runtime_overview import RuntimeOverview, RuntimeSnapshot
from mlx_studio_runtime.application.speech_generation_service import SpeechGenerationService
from mlx_studio_runtime.application.voice_profile_service import VoiceProfileService


class RuntimeApplication:
    def __init__(self, store: SQLiteRepositories, runtime_source: Path) -> None:
        self.store = store
        self.events = EventHub()
        self.started_at = time.monotonic()
        store.jobs.recover_interrupted("RUNTIME_RESTARTED")
        recover_media(store.database)
        self.catalog = ModelCatalog(
            store.models,
            self.events,
            manifest_from_directory,
            lambda model, path: self.scheduler.check_model_available(model, path),
        )
        self.inference = ModelRuntime(
            self.catalog.models,
            store.models,
            self.events,
            lambda: WorkerHost(
                runtime_source, store.media_path / "images", store.media_path / "audio"
            ),
        )
        self.lifecycle = JobLifecycle(store.jobs, self.events, store.database.transaction)
        self.scheduler = JobScheduler(self.lifecycle, self.inference)
        self.agent_host = AgentHost(store.database_path.parent / "coding")
        self.coding_identity = coding_model_identity
        self.coding = CodingGateway(self.agent_host.request)
        self.provider_inference = InferenceService(self.scheduler)
        self.controls = RuntimeControl(self.scheduler, self.inference)
        self.queries = Queries(
            store.conversations,
            store.jobs,
            store.images,
            self.lifecycle,
            ImageFiles(store.media_path).read,
        )
        attachment_files = AttachmentFiles(store.attachments, store.media_path)
        self.attachments = Attachments(attachment_files.upload, attachment_files.read)
        self.downloads = Downloads(download_model, self.catalog)
        self.chat = ChatService(
            store.conversations,
            attachment_files.paths,
            self.catalog.models,
            self.scheduler,
            self.inference,
            SubmissionJournal(store.database),
        )
        self.images = self._image_service(store, attachment_files)
        audio_files = AudioFiles(store.media_path)
        self.voices = VoiceProfileService(store.audio, audio_files)
        self.speech = SpeechGenerationService(
            self.catalog.models,
            self.scheduler,
            self.inference,
            store.audio,
            audio_files,
            self.voices,
        )
        self.overview = RuntimeOverview(
            self._overview_snapshot,
            HostDiagnostics(
                store.database_path.parent,
                lambda: self.inference.worker.pid if self.inference.worker else None,
            ),
        )
        self.model_removal = RemoveModel(
            ModelRemovalPorts(
                self.catalog.models.get,
                self.catalog.remove_registration,
                self.scheduler.reserve_removal,
                self.controls.unload_reserved,
                self.catalog.shared_path,
            ),
            ManagedModelFiles(),
        )

    def _image_service(
        self, store: SQLiteRepositories, attachments: AttachmentFiles
    ) -> ImageGenerationService:
        return ImageGenerationService(
            self.catalog.models,
            self.scheduler,
            self.inference,
            store.images,
            ImageFiles(store.media_path),
            attachments.paths,
        )

    async def close(self) -> None:
        await self.agent_host.close()
        await self.scheduler.close()
        self.store.close()

    def _overview_snapshot(self) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            state=self.inference.state.value,
            active_model_id=self.inference.active_model_id,
            worker_restarts=self.inference.worker_restarts,
            active_jobs=sum(
                job.state.value in {"preparing", "running", "cancelling"}
                for job in self.lifecycle.items.values()
            ),
            model_engines=tuple(model.engine for model in self.catalog.models.values()),
            job_states=tuple(str(job["state"]) for job in self.queries.list_jobs()),
            event_sequence=self.events.sequence,
            instance_id=self.events.instance_id,
        )
