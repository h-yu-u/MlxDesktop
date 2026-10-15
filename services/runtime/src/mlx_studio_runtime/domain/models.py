"""Model metadata and capability derivation from static files only."""

from dataclasses import dataclass
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
    managed_installation: bool = False
    artifact_identity: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "installationId": self.id,
            "managedInstallation": self.managed_installation,
            "artifactIdentity": self.artifact_identity,
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


def infer_model_kind(
    config: dict[str, object],
    model_index: dict[str, object],
) -> tuple[EngineName, TaskName]:
    pipeline = str(model_index.get("_class_name", "")).lower().replace("_", "")
    model_type = str(config.get("model_type", "")).lower()
    raw_architectures = config.get("architectures")
    architectures = (
        cast(list[object], raw_architectures) if isinstance(raw_architectures, list) else []
    )
    architecture_text = " ".join(
        str(item).lower() for item in architectures if isinstance(item, str)
    )
    image_pipeline_markers = (
        "diffusionpipeline",
        "fluxpipeline",
        "stablediffusion",
        "zimage",
        "qwenimage",
    )
    image_model_types = {
        "flux",
        "stable_diffusion",
        "z_image",
        "zimage",
        "qwen_image",
        "qwen_image_21",
    }
    if any(marker in pipeline for marker in image_pipeline_markers) or (
        model_type in image_model_types
    ):
        return "mflux", "image-generation"
    vision_markers = (
        "vision",
        "llava",
        "paligemma",
        "idefics",
        "mllama",
        "pixtral",
        "internvl",
        "qwen2vl",
        "qwen25vl",
        "qwen3vl",
        "smolvlm",
        "phi3v",
        "florence",
        "molmo",
    )
    description = f"{model_type} {architecture_text}".replace("_", "").replace("-", "")
    if isinstance(config.get("vision_config"), dict) or any(
        marker in description for marker in vision_markers
    ):
        return "mlx-vlm", "vision-language"
    return "mlx-lm", "text-generation"


def stable_metadata(metadata: dict[str, object]) -> dict[str, object]:
    """Remove location-specific fields before deriving model identity."""
    return {
        key: value
        for key, value in metadata.items()
        if key not in {"_name_or_path", "name_or_path"}
    }


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
    capability_value = value.get("capabilities")
    capabilities = (
        cast(dict[str, object], capability_value) if isinstance(capability_value, dict) else {}
    )
    compatibility_value = value.get("compatibility")
    compatibility = (
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
    inputs = value.get("inputModalities")
    outputs = value.get("outputModalities")
    if not isinstance(inputs, list) or not isinstance(outputs, list):
        raise ValueError("MODEL_METADATA_INVALID")
    status = compatibility.get("status", "unknown")
    if status not in {"unknown", "supported", "partial", "incompatible", "broken"}:
        status = "unknown"
    context_length = value.get("contextLength")
    disk_size = value.get("diskSizeBytes")
    memory = value.get("estimatedMemoryBytes")
    return ModelManifest(
        id=str(value["id"]),
        display_name=str(value["displayName"]),
        source=cast(ModelSource, source),
        local_path=str(value["localPath"]),
        engine=cast(EngineName, engine),
        task=cast(TaskName, task),
        input_modalities=tuple(str(item) for item in inputs),
        output_modalities=tuple(str(item) for item in outputs),
        compatibility_status=cast(CompatibilityStatus, status),
        revision=str(value["revision"]) if value.get("revision") is not None else None,
        context_length=context_length if isinstance(context_length, int) else None,
        disk_size_bytes=disk_size if isinstance(disk_size, int) else None,
        estimated_memory_bytes=memory if isinstance(memory, int) else None,
        capabilities=ModelCapabilities(
            streaming=capabilities.get("streaming") is True,
            thinking=capabilities.get("thinking") is True,
            tools=capabilities.get("tools") is True,
            structured_output=capabilities.get("structuredOutput") is True,
            multi_image=capabilities.get("multiImage") is True,
            image_editing=capabilities.get("imageEditing") is True,
            inpainting=capabilities.get("inpainting") is True,
            lora=capabilities.get("lora") is True,
        ),
        managed_installation=value.get("managedInstallation") is True,
        artifact_identity=str(value["artifactIdentity"]) if value.get("artifactIdentity") else None,
    )
