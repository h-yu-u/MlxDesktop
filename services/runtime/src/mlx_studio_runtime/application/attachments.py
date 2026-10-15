"""Attachment use cases depend only on bounded file storage."""

from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any


class Attachments:
    def __init__(
        self,
        upload: Callable[[AsyncIterator[bytes], str], Awaitable[dict[str, Any]]],
        read: Callable[[str], tuple[Path, dict[str, Any]]],
    ) -> None:
        self.upload = upload
        self.read = read
