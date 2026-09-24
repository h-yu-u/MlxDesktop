"""Pure-ish chat request validation and context construction."""

from mlx_studio_runtime.adapters.persistence.sqlite_store import SQLiteStore
from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.domain.models import ModelManifest


def validate_attachments(model: ModelManifest, attachment_ids: list[str]) -> None:
    if attachment_ids and "image" not in model.input_modalities:
        raise RuntimeFault(
            RuntimeErrorInfo("MODEL_INPUT_UNSUPPORTED", "当前模型不支持图片输入")
        )
    if attachment_ids and model.engine != "mlx-vlm":
        raise RuntimeFault(
            RuntimeErrorInfo("ENGINE_NOT_AVAILABLE", "此图片模型尚未通过 Runtime 验证")
        )
    if len(attachment_ids) > 1 and not model.capabilities.multi_image:
        raise RuntimeFault(
            RuntimeErrorInfo("MODEL_INPUT_UNSUPPORTED", "当前模型仅声明支持单图片输入")
        )


def attachment_paths(store: SQLiteStore, attachment_ids: list[str]) -> list[str]:
    attachments = store.get_attachments(attachment_ids)
    if attachments is None:
        raise RuntimeFault(RuntimeErrorInfo("ATTACHMENT_NOT_FOUND", "请求包含不存在的附件"))
    return [
        str((store.media_path / str(item["relativePath"])).resolve())
        for item in attachments
    ]


def conversation_context(
    store: SQLiteStore,
    conversation_id: str,
    turn_id: str,
) -> list[dict[str, str]]:
    conversation = store.get_conversation(conversation_id) or {"messages": []}
    context: list[dict[str, str]] = []
    for message in conversation.get("messages", []):
        role = message.get("role")
        content = message.get("content")
        if isinstance(role, str) and role in {"user", "assistant", "system"} and isinstance(
            content, str
        ):
            context.append({"role": role, "content": content})
        if message.get("turnId") == turn_id and role == "user":
            break
    return context
