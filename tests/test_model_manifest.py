import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "services" / "runtime" / "src"))

from mlx_studio_runtime.domain.models import manifest_from_directory


class ModelManifestTests(unittest.TestCase):
    def test_model_id_is_stable_when_directory_moves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first"
            second = Path(directory) / "second"
            first.mkdir()
            (first / "config.json").write_text(
                json.dumps(
                    {
                        "model_type": "llama",
                        "max_position_embeddings": 4096,
                        "_name_or_path": str(first),
                    }
                ),
                encoding="utf-8",
            )
            (first / "model.safetensors").write_bytes(b"weights")
            original = manifest_from_directory(first)
            shutil.move(first, second)
            (second / "config.json").write_text(
                json.dumps(
                    {
                        "model_type": "llama",
                        "max_position_embeddings": 4096,
                        "_name_or_path": str(second),
                    }
                ),
                encoding="utf-8",
            )
            moved = manifest_from_directory(second)
            self.assertEqual(original.id, moved.id)
            self.assertNotEqual(original.local_path, moved.local_path)

    def test_stablelm_is_not_misclassified_as_an_image_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "stablelm"
            root.mkdir()
            (root / "config.json").write_text(
                json.dumps(
                    {"model_type": "stablelm", "architectures": ["StableLmForCausalLM"]}
                ),
                encoding="utf-8",
            )
            (root / "weights.safetensors").write_bytes(b"weights")
            self.assertEqual(manifest_from_directory(root).engine, "mlx-lm")

    def test_static_metadata_distinguishes_vlm_and_image_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vlm = root / "vlm"
            vlm.mkdir()
            (vlm / "config.json").write_text(
                json.dumps({"model_type": "qwen2_vl", "architectures": ["Qwen2VL"]}),
                encoding="utf-8",
            )
            image = root / "image"
            image.mkdir()
            (image / "model_index.json").write_text(
                json.dumps({"_class_name": "FluxPipeline"}),
                encoding="utf-8",
            )
            self.assertEqual(manifest_from_directory(vlm).engine, "mlx-vlm")
            self.assertEqual(manifest_from_directory(image).engine, "mflux")


if __name__ == "__main__":
    unittest.main()
