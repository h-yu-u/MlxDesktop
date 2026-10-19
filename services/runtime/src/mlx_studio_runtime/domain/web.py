"""Immutable web configuration and retrieval values."""

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault


@dataclass(frozen=True)
class WebConfig:
    id: str
    revision: int
    provider: str
    base_url: str
    secret_ref: str | None
    timeout_seconds: int = 30
    max_results: int = 6


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    published_at: str | None = None


@dataclass(frozen=True)
class PageRead:
    url: str
    text: str


def normalize_base_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeFault(RuntimeErrorInfo("WEB_CONFIG_INVALID", "请输入有效的搜索服务地址"))
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeFault(RuntimeErrorInfo("WEB_CONFIG_INVALID", "远程搜索服务必须使用 HTTPS"))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))
