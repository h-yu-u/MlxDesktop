"""Hugging Face download boundary with per-revision installation directories."""

import asyncio
import hashlib
import os
from pathlib import Path

from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault


async def download_model(repo_id: str, revision: str | None) -> tuple[Path, str]:
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError as error:
        raise RuntimeFault(
            RuntimeErrorInfo("DOWNLOAD_ADAPTER_UNAVAILABLE", "下载组件未安装")
        ) from error
    root = Path(os.getenv("MLX_STUDIO_MODELS_DIR", Path.home() / "MLXModels")).expanduser()
    try:
        metadata = await asyncio.to_thread(HfApi().model_info, repo_id, revision=revision)
        resolved_revision = metadata.sha
        if not resolved_revision:
            raise ValueError("MODEL_REVISION_UNRESOLVED")
        target = (
            root
            / repo_id.replace("/", "--")
            / hashlib.sha256(resolved_revision.encode()).hexdigest()[:16]
        )
        target.mkdir(parents=True, exist_ok=True)
        path = await asyncio.to_thread(
            snapshot_download, repo_id=repo_id, revision=resolved_revision, local_dir=str(target)
        )
    except Exception as error:  # Download boundary retains upstream cause without exposing it.
        raise RuntimeFault(
            RuntimeErrorInfo("MODEL_DOWNLOAD_FAILED", "模型下载失败", True)
        ) from error
    if Path(path).resolve() != target.resolve():
        raise RuntimeFault(RuntimeErrorInfo("MODEL_DOWNLOAD_FAILED", "下载目录不符合托管安装记录"))
    return Path(path), resolved_revision
