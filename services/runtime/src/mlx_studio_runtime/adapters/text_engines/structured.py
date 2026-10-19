"""One tool-aware Worker request. Native formats never leak into product tools."""

import json
import re
import sys
import uuid
from contextlib import redirect_stdout
from typing import Any


def parse_completion(
    text: str, tools: list[dict[str, Any]], reason: str, parser: str = "json"
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": text}
    if "<tool_call>" not in text:
        if "</tool_call>" in text:
            raise ValueError("TOOL_FORMAT_INVALID")
        return {"message": message, "finish_reason": reason}
    if reason == "length":
        raise ValueError("TOOL_OUTPUT_TRUNCATED")
    fragments = re.findall(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL)
    if (
        not 1 <= len(fragments) <= 48
        or len(fragments) != text.count("<tool_call>")
        or len(fragments) != text.count("</tool_call>")
    ):
        raise ValueError("TOOL_FORMAT_INVALID")
    # Parse the whole batch before returning any calls. Pi executes our tools sequentially.
    message["tool_calls"] = [parse_call(fragment.strip(), tools, parser) for fragment in fragments]
    message["content"] = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.DOTALL)
    return {"message": message, "finish_reason": "tool_calls"}


def parse_call(text: str, tools: list[dict[str, Any]], parser: str) -> dict[str, Any]:
    try:
        value = parse_xml_call(text, tools) if parser == "qwen-xml" else json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("TOOL_JSON_INVALID") from error
    if not isinstance(value, dict) or not isinstance(value.get("arguments"), dict):
        raise ValueError("TOOL_ARGUMENTS_INVALID")
    name = value.get("name")
    if name not in {tool["function"]["name"] for tool in tools}:
        raise ValueError("UNKNOWN_TOOL")
    return {
        "id": f"call_{uuid.uuid4().hex}",
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(value["arguments"], ensure_ascii=False),
        },
    }


def parse_xml_call(text: str, tools: list[dict[str, Any]]) -> dict[str, Any]:
    match = re.fullmatch(r"<function=([A-Za-z0-9_]+)>(.*?)</function>", text, re.DOTALL)
    if match is None:
        raise ValueError("TOOL_XML_INVALID")
    name, body = match.groups()
    schema = next(
        (tool["function"]["parameters"] for tool in tools if tool["function"]["name"] == name), None
    )
    if schema is None:
        raise ValueError("UNKNOWN_TOOL")
    args: dict[str, object] = {}
    parameters = re.findall(r"<parameter=([A-Za-z0-9_]+)>(.*?)</parameter>", body, re.DOTALL)
    if re.sub(r"<parameter=[A-Za-z0-9_]+>.*?</parameter>", "", body, flags=re.DOTALL).strip():
        raise ValueError("TOOL_XML_INVALID")
    for key, value in parameters:
        if key in args or key not in schema.get("properties", {}):
            raise ValueError("TOOL_ARGUMENTS_INVALID")
        definition = schema["properties"][key]
        value = value.removeprefix("\n").removesuffix("\n")
        alternatives = definition.get("anyOf", [])
        allows_null = definition.get("type") == "null" or any(
            item.get("type") == "null" for item in alternatives
        )
        if value.strip() == "null" and allows_null:
            args[key] = None
        elif definition.get("type", "string") == "string":
            args[key] = value
        else:
            args[key] = json.loads(value)
    if any(key not in args for key in schema.get("required", [])):
        raise ValueError("TOOL_ARGUMENTS_INVALID")
    return {"name": name, "arguments": args}


def scripted_reply(payload: dict[str, Any]) -> str:
    """Deterministic failing-check/repair provider exercised through the real Pi SDK."""
    messages = payload["messages"]
    probe = any("Coding capability probe:" in str(item.get("content")) for item in messages)
    if not probe:
        return "Fake Coding provider：仅用于开发协议验证。请验证并选择真实本地模型。"
    previous = [item for item in messages if item["role"] == "tool"]
    name, args = "read", {"path": "probe.txt"}
    if previous:
        calls = [call for item in messages for call in item.get("tool_calls", [])]
        last_name = calls[-1]["function"]["name"]
        if last_name == "read":
            result = json.loads(previous[-1]["content"])
            # First attempt deliberately fails to prove that the agent uses tool evidence.
            content = (
                "after\n"
                if any(
                    '"exitCode":1' in str(item.get("content", "")).replace(" ", "")
                    for item in previous
                )
                else "broken\n"
            )
            name, args = (
                "write",
                {"path": "probe.txt", "content": content, "expectedHash": result["sha256"]},
            )
        elif last_name == "write":
            name, args = "run_command", {"command": "/usr/bin/grep -qx 'after' probe.txt"}
        elif last_name == "run_command":
            result = json.loads(previous[-1]["content"])
            if result["exitCode"] == 0:
                return "已读取并修改 probe.txt，失败后修复，验证退出码为 0。"
    prefix = '<tool_call>{"name":"list","arguments":{}}</tool_call>\n' if not previous else ""
    return (
        prefix
        + "<tool_call>"
        + json.dumps({"name": name, "arguments": args}, ensure_ascii=False)
        + "</tool_call>"
    )


def generate_structured(session: Any, payload: dict[str, Any]) -> None:
    job_id = str(payload["job_id"])
    session.finish_reason = "stop"
    session.generation_tokens = 0
    session.emit("generation.started", {"job_id": job_id})
    try:
        parser = "json"
        if session.engine == "fake":
            text = scripted_reply(payload)
        else:
            tokenizer = (
                session.tokenizer if session.engine == "mlx-lm" else session.processor.tokenizer
            )
            template = tokenizer.chat_template
            if not isinstance(template, str) or "<tool_call>" not in template:
                raise ValueError("TOOL_TEMPLATE_UNSUPPORTED")
            parser = "qwen-xml" if "<function=" in template else "json"
            messages = []
            for item in payload["messages"]:
                value = dict(item)
                if "tool_calls" in value:
                    value["tool_calls"] = [
                        {
                            **call,
                            "function": {
                                **call["function"],
                                "arguments": json.loads(call["function"]["arguments"]),
                            },
                        }
                        for call in value["tool_calls"]
                    ]
                messages.append(value)
            with redirect_stdout(sys.stderr):
                rendered = tokenizer.apply_chat_template(
                    messages,
                    tools=payload["tools"],
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
                # The rendered prompt is already tool-aware; don't normalize or re-template it.
                text = _generate_native(session, rendered, payload)
        if session.cancel.is_set() or session.shutdown.is_set():
            session.emit("generation.cancelled", {"job_id": job_id})
            return
        result = parse_completion(text, payload["tools"], session.finish_reason, parser)
        session.emit(
            "generation.result",
            {"job_id": job_id, **result, "generation_tokens": session.generation_tokens},
        )
        session.emit(
            "generation.completed", {"job_id": job_id, "finish_reason": result["finish_reason"]}
        )
    except Exception as error:  # Worker boundary, sanitized error code only.
        session.emit(
            "generation.failed",
            {
                "job_id": job_id,
                "error_code": str(error)
                if isinstance(error, ValueError)
                else "STRUCTURED_INFERENCE_FAILED",
            },
        )


def _generate_native(session: Any, rendered: str, payload: dict[str, Any]) -> str:
    if session.engine == "mlx-lm":
        from mlx_lm import stream_generate  # type: ignore[import-not-found]
        from mlx_lm.sample_utils import make_sampler  # type: ignore[import-not-found]

        responses = stream_generate(
            session.model,
            session.tokenizer,
            rendered,
            max_tokens=payload["max_tokens"],
            sampler=make_sampler(temp=payload["temperature"]),
        )
    elif session.engine == "mlx-vlm":
        from mlx_vlm import stream_generate  # type: ignore[import-not-found]

        responses = stream_generate(
            model=session.model,
            processor=session.processor,
            prompt=rendered,
            max_tokens=payload["max_tokens"],
            temperature=payload["temperature"],
            verbose=False,
        )
    else:
        raise ValueError("TOOL_ENGINE_UNSUPPORTED")
    parts: list[str] = []
    for response in responses:
        if session.cancel.is_set() or session.shutdown.is_set():
            break
        session.record_completion(response)
        parts.append(str(response.text))
    if session.generation_tokens >= payload["max_tokens"]:
        session.finish_reason = "length"
    return "".join(parts)
