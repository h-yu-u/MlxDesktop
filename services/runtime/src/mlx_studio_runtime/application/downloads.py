"""Download validation and registration; no network or filesystem implementation."""

import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from mlx_studio_runtime.application.model_catalog import ModelCatalog
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault


class Downloads:
    def __init__(
        self,
        download: Callable[[str, str | None], Awaitable[tuple[Path, str]]],
        catalog: ModelCatalog,
    ) -> None:
        self.download = download
        self.catalog = catalog

    async def pull(self, repo_id: str, revision: str | None) -> dict[str, str]:
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo_id) or ".." in repo_id:
            raise RuntimeFault(RuntimeErrorInfo("MODEL_REPO_ID_INVALID", "模型仓库编号无效"))
        path, resolved_revision = await self.download(repo_id, revision)
        manifest = await self.catalog.scan_model(
            path,
            source="huggingface",
            revision=resolved_revision,
            display_name=repo_id,
            managed_installation=True,
        )
        return {"modelId": str(manifest["id"]), "state": "available"}
