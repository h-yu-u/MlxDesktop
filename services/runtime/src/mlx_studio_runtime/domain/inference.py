"""Validate structural context without silently replacing unsupported messages."""

import json
from typing import Any


def validate_context(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> None:
    names = [tool["function"]["name"] for tool in tools]
    if len(set(names)) != len(names):
        raise ValueError("DUPLICATE_TOOL_NAME")
    seen: set[str] = set()
    pending: set[str] = set()
    for message in messages:
        role = message["role"]
        if pending and role != "tool":
            raise ValueError("TOOL_RESULTS_MISSING")
        if role == "tool":
            call_id = message.get("tool_call_id")
            if call_id not in pending:
                raise ValueError("TOOL_RESULT_ID_INVALID")
            pending.remove(call_id)
        calls = message.get("tool_calls", [])
        if calls and role != "assistant":
            raise ValueError("TOOL_CALL_ROLE_INVALID")
        for call in calls:
            if call["id"] in seen:
                raise ValueError("DUPLICATE_TOOL_ID")
            args = json.loads(call["function"]["arguments"])
            if not isinstance(args, dict):
                raise ValueError("TOOL_ARGUMENTS_INVALID")
            seen.add(call["id"])
            pending.add(call["id"])
    if pending:
        raise ValueError("TOOL_RESULTS_MISSING")
