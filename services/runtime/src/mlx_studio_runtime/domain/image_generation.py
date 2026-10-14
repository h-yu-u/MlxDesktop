"""Image request invariants and an immutable reproducible parameter snapshot."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ImageParameters:
    model_id: str
    prompt: str
    width: int
    height: int
    steps: int
    seed: int

    def __post_init__(self) -> None:
        if not self.model_id or not self.prompt.strip() or len(self.prompt) > 10_000:
            raise ValueError("IMAGE_PROMPT_INVALID")
        if any(value < 64 or value > 2048 or value % 16 for value in (self.width, self.height)):
            raise ValueError("IMAGE_DIMENSIONS_INVALID")
        if not 1 <= self.steps <= 100 or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("IMAGE_PARAMETERS_INVALID")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def fake_image_manifest_dict() -> dict[str, object]:
    return {
        "id": "builtin-fake-image",
        "displayName": "Fake Image Engine (Development)",
        "source": "builtin",
        "localPath": "fake://image",
        "engine": "fake",
        "task": "image-generation",
        "inputModalities": ["text"],
        "outputModalities": ["image"],
        "compatibility": {"status": "supported"},
        "capabilities": {},
    }
