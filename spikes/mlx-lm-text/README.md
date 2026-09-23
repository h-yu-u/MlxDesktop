# P0-02：mlx-lm 文本推理 Spike

用独立 Python 环境验证官方 `mlx-lm` Python API 的模型加载、聊天模板和流式生成。默认模型为约 290 MB 的 4-bit Qwen2.5-0.5B Instruct；下载模型需要访问 Hugging Face。模型 revision 固定到本次验证用的提交，后续由 P0-09 兼容矩阵决定正式基线。

## 运行

在 Apple Silicon Mac 上执行：

```bash
uv run --project spikes/mlx-lm-text --python 3.12 python spikes/mlx-lm-text/run_text_generation.py
```

首次运行会准备 Python 3.12 和 `mlx-lm`，并下载模型文件。可以通过 `--model`、`--revision`、`--prompt` 和 `--max-tokens` 覆盖默认值。生成文本输出到 stdout，耗时、吞吐、峰值内存、生成 token 数和终态摘要输出到 stderr；脚本不持久化 prompt 或输出。

脚本将 `trust_remote_code` 显式关闭。成功代表本机完成模型加载并收到非空的逐步生成结果；这不是取消、错误恢复或模型卸载验证，这些留给 P0-05 / P0-06。
