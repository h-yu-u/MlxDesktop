# P0-03：mlx-vlm 图片理解 Spike

```bash
uv run --project spikes/mlx-vlm-image --python 3.12 python spikes/mlx-vlm-image/run_vlm.py --image /path/to/image.png
```

默认使用候选小型 VLM；可传 `--model`、`--prompt` 和 `--max-tokens`。模型与输入图需从本机可读路径获取；输入上限为 50 MB。执行 `mlx_vlm.load` 时显式关闭 `trust_remote_code`。

该 spike 使用 `load`、`load_config`、`apply_chat_template`、`generate` 的 Python API。当前代码未能在本机运行，模型兼容性仍待 Apple Silicon + 可访问模型源的环境验证。
