"""Stable application error codes independent of upstream exception text."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeErrorInfo:
    code: str
    message: str
    retryable: bool = False
    details: dict[str, str] | None = None


class RuntimeFault(Exception):
    def __init__(self, info: RuntimeErrorInfo) -> None:
        super().__init__(info.message)
        self.info = info


def error_payload(error: RuntimeFault, request_id: str) -> dict[str, object]:
    return {
        "error": {
            "code": error.info.code,
            "message": error.info.message,
            "retryable": error.info.retryable,
            "details": error.info.details or {},
            "request_id": request_id,
        }
    }
