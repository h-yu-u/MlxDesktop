"""Model metadata and capability derivation from static files only."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

EngineName = Literal["mlx-lm", "mlx-vlm", "mflux", "fake"]
TaskName = Literal["text-generation", "vision-language", "image-generation"]
ModelSource = Literal["huggingface", "local", "builtin"]
CompatibilityStatus = Literal["unknown", "supported", "partial", "incompatible", "broken"]


@dataclass(frozen=True)
class ModelCapabilities:
    streaming: bool = False
    thinking: bool = False
    tools: bool = False
    structured_output: bool = False
    multi_image: bool = False
    image_editing: bool = False
    inpainting: bool = False
    lora: bool = False


@dataclass(frozen=True)
class ModelManifest:
    id: str
    display_name: str
    source: ModelSource
    local_path: str
    engine: EngineName
    task: TaskName
    input_modalities: tuple[str, ...]
    output_modalities: tuple[str, ...]
    compatibility_status: CompatibilityStatus = "unknown"
    revision: str | None = None
    context_length: int | None = None
    disk_size_bytes: int | None = None
    estimated_memory_bytes: int | None = None
    capabilities: ModelCapabilities = ModelCapabilities()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "displayName": self.display_name,
            "source": self.source,
            "localPath": self.local_path,
            "engine": self.engine,
            "task": self.task,
            "inputModalities": list(self.input_modalities),
            "outputModalities": list(self.output_modalities),
            "revision": self.revision,
            "contextLength": self.context_length,
            "diskSizeBytes": self.disk_size_bytes,
            "estimatedMemoryBytes": self.estimated_memory_bytes,
            "compatibility": {"status": self.compatibility_status},
            "capabilities": {
                "streaming": self.capabilities.streaming,
                "thinking": self.capabilities.thinking,
                "tools": self.capabilities.tools,
                "structuredOutput": self.capabilities.structured_output,
                "multiImage": self.capabilities.multi_image,
                "imageEditing": self.capabilities.image_editing,
                "inpainting": self.capabilities.inpainting,
                "lora": self.capabilities.lora,
            },
        }


def manifest_from_directory(path: Path) -> ModelManifest:
    """Read JSON model metadata without importing/executing model code."""
    config_path = path / "config.json"
    if not config_path.is_file() or config_path.stat().st_size > 2_000_000:
        raise ValueError("MODEL_METADATA_INVALID")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    vision_config = config.get("vision_config")
    engine: EngineName = "mlx-vlm" if isinstance(vision_config, dict) else "mlx-lm"
    task: TaskName = "vision-language" if engine == "mlx-vlm" else "text-generation"
    input_modalities = ("text", "image") if task == "vision-language" else ("text",)
    context_length = config.get("max_position_embeddings")
    size = sum(file.stat().st_size for file in path.glob("*.safetensors") if file.is_file())
    manifest_id = path.resolve().as_posix().replace("/", "_").strip("_")[-120:]
    return ModelManifest(
        id=f"local-{manifest_id}",
        display_name=str(config.get("_name_or_path") or path.name),
        source="local",
        local_path=str(path.resolve()),
        engine=engine,
        task=task,
        input_modalities=input_modalities,
        output_modalities=("text",),
        context_length=context_length if isinstance(context_length, int) else None,
        disk_size_bytes=size,
        capabilities=ModelCapabilities(streaming=engine == "mlx-lm", multi_image=False),
    )


def fake_text_manifest() -> ModelManifest:
    return ModelManifest(
        id="builtin-fake-text",
        display_name="Fake Text Engine (Development)",
        source="builtin",
        local_path="fake://text",
        engine="fake",
        task="text-generation",
        input_modalities=("text",),
        output_modalities=("text",),
        compatibility_status="supported",
        capabilities=ModelCapabilities(streaming=True, structured_output=True),
    )


def manifest_from_dict(value: dict[str, object]) -> ModelManifest:
    """Restore a persisted manifest without reading or executing model code."""
    capabilities_value = value.get("capabilities")
    capability_data = (
        cast(dict[str, object], capabilities_value) if isinstance(capabilities_value, dict) else {}
    )
    compatibility_value = value.get("compatibility")
    compatibility_data = (
        cast(dict[str, object], compatibility_value)
        if isinstance(compatibility_value, dict)
        else {}
    )
    engine = value.get("engine")
    task = value.get("task")
    source = value.get("source")
    if engine not in {"mlx-lm", "mlx-vlm", "mflux", "fake"}:
        raise ValueError("MODEL_METADATA_INVALID")
    if task not in {"text-generation", "vision-language", "image-generation"}:
        raise ValueError("MODEL_METADATA_INVALID")
    if source not in {"huggingface", "local", "builtin"}:
        raise ValueError("MODEL_METADATA_INVALID")
    input_modalities = value.get("inputModalities")
    output_modalities = value.get("outputModalities")
    if not isinstance(input_modalities, list) or not isinstance(output_modalities, list):
        raise ValueError("MODEL_METADATA_INVALID")
    flags = {
        "streaming": "streaming",
        "thinking": "thinking",
        "tools": "tools",
        "structured_output": "structuredOutput",
        "multi_image": "multiImage",
        "image_editing": "imageEditing",
        "inpainting": "inpainting",
        "lora": "lora",
    }
    capabilities = ModelCapabilities(
        **{field: capability_data.get(key, False) is True for field, key in flags.items()}
    )
    status = compatibility_data.get("status", "unknown")
    if status not in {"unknown", "supported", "partial", "incompatible", "broken"}:
        status = "unknown"
    restored_context_length = value.get("contextLength")
    restored_disk_size = value.get("diskSizeBytes")
    restored_memory = value.get("estimatedMemoryBytes")
    return ModelManifest(
        id=str(value["id"]),
        display_name=str(value["displayName"]),
        source=cast(ModelSource, source),
        local_path=str(value["localPath"]),
        engine=cast(EngineName, engine),
        task=cast(TaskName, task),
        input_modalities=tuple(str(item) for item in input_modalities),
        output_modalities=tuple(str(item) for item in output_modalities),
        compatibility_status=cast(CompatibilityStatus, status),
        revision=str(value["revision"]) if value.get("revision") is not None else None,
        context_length=restored_context_length
        if isinstance(restored_context_length, int)
        else None,
        disk_size_bytes=restored_disk_size if isinstance(restored_disk_size, int) else None,
        estimated_memory_bytes=restored_memory if isinstance(restored_memory, int) else None,
        capabilities=capabilities,
    )
