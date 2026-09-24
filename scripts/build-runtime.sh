#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
runtime_project="$repo_root/services/runtime"
target_triple="aarch64-apple-darwin"
output_directory="$repo_root/apps/desktop/src-tauri/binaries"
build_directory="$repo_root/.build/runtime"

mkdir -p "$output_directory"
if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "Runtime sidecar must be built on Apple Silicon macOS (arm64)." >&2
  exit 2
fi

uv run --frozen --project "$runtime_project" --python 3.12 \
  --extra mlx-lm --extra mlx-vlm --extra mflux --with pyinstaller \
  pyinstaller --clean --noconfirm --onefile \
  --name mlx-studio-runtime \
  --distpath "$build_directory/dist" \
  --workpath "$build_directory/work" \
  --specpath "$build_directory/spec" \
  --paths "$runtime_project/src" \
  --collect-all mlx_studio_runtime \
  --collect-all mlx_lm \
  --collect-all mlx_vlm \
  --collect-all mflux \
  "$runtime_project/src/mlx_studio_runtime/entrypoints/http/main.py"

install -m 755 "$build_directory/dist/mlx-studio-runtime" \
  "$output_directory/mlx-studio-runtime-$target_triple"
