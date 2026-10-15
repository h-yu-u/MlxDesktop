"""Attachment byte streams and safe managed media paths."""

import hashlib
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from mlx_studio_runtime.adapters.persistence.attachment_repository import AttachmentRepository
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault


async def save_attachment(
    chunks: AsyncIterator[bytes], filename: str, store: AttachmentRepository, root: Path
) -> dict[str, Any]:
    max_bytes = 20 * 1024 * 1024
    attachment_id = str(uuid.uuid4())
    attachment_dir = root / "attachments"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    temp_path = attachment_dir / f".{attachment_id}.upload"
    digest = hashlib.sha256()
    header = bytearray()
    size = 0
    try:
        with temp_path.open("wb") as output:
            async for chunk in chunks:
                size += len(chunk)
                if size > max_bytes:
                    raise RuntimeFault(RuntimeErrorInfo("ATTACHMENT_TOO_LARGE", "图片超过大小限制"))
                if len(header) < 16:
                    header.extend(chunk[: 16 - len(header)])
                digest.update(chunk)
                output.write(chunk)
        mime_type = _image_mime(bytes(header))
        if mime_type is None or size == 0:
            raise RuntimeFault(RuntimeErrorInfo("IMAGE_FORMAT_UNSUPPORTED", "图片格式无效"))
        safe_name = Path(filename.replace("\\", "/")).name[:180] or "image"
        relative_path = f"attachments/{attachment_id}"
        final_path = root / relative_path
        temp_path.replace(final_path)
        item = {
            "id": attachment_id,
            "sha256": digest.hexdigest(),
            "mimeType": mime_type,
            "sizeBytes": size,
            "relativePath": relative_path,
            "originalName": safe_name,
        }
        store.save(item)
        return {key: item[key] for key in ("id", "sha256", "mimeType", "sizeBytes", "originalName")}
    except BaseException:
        temp_path.unlink(missing_ok=True)
        (root / f"attachments/{attachment_id}").unlink(missing_ok=True)
        raise


def _image_mime(header: bytes) -> str | None:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None


class AttachmentFiles:
    def __init__(self, store: AttachmentRepository, media_path: Path) -> None:
        self.store = store
        self.media_path = media_path

    async def upload(self, chunks: AsyncIterator[bytes], filename: str) -> dict[str, Any]:
        return await save_attachment(chunks, filename, self.store, self.media_path)

    def read(self, attachment_id: str) -> tuple[Path, dict[str, Any]]:
        items = self.store.get_many([attachment_id])
        if not items:
            raise RuntimeFault(RuntimeErrorInfo("ATTACHMENT_NOT_FOUND", "找不到此附件"))
        item = items[0]
        root = (self.media_path / "attachments").resolve()
        path = (self.media_path / item["relativePath"]).resolve()
        if path.parent != root or not path.is_file():
            raise RuntimeFault(
                RuntimeErrorInfo("ATTACHMENT_NOT_FOUND", "附件文件已不存在或路径无效")
            )
        return path, item

    def paths(self, attachment_ids: list[str]) -> list[str]:
        return [str(self.read(attachment_id)[0]) for attachment_id in attachment_ids]
