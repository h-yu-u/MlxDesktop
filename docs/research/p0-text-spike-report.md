# P0-02：mlx-lm 文本推理 Spike 记录

状态：**待真实模型运行**

## 已完成

- 新增独立 Spike，使用 `mlx_lm.load` 加载固定 revision 的 `mlx-community/Qwen2.5-0.5B-Instruct-4bit`。
- 使用 tokenizer chat template 构造 prompt，再通过 `mlx_lm.stream_generate` 输出增量文本。
- 记录首 token、首段文本、生成 token 数、tokens/s、峰值内存和结束原因；prompt 与模型输出不写文件。
- 显式关闭 `trust_remote_code`。
- Fake stream 用例覆盖增量输出、指标收集和空生成失败路径。

## 本机验证情况

本机是 Apple M5 Pro / arm64，系统 Python 为 3.9.6，低于产品指定 Python 3.12。uv 已有 Python 3.11，但没有 3.12。

- Python 3.12 隔离环境准备在下载解释器阶段长时间无进展，已停止。
- 使用现有 Python 3.11 尝试依赖安装时，多个包成功下载，但 `mlx-metal==0.32.2` 的 macOS wheel 未能取回；离线重试确认该 wheel 不在缓存中。
- 因 MLX 依赖没有安装，Hugging Face 模型尚未下载，也没有真实推理结论。
- 7 个本地单元测试通过；这些测试只验证探针解析和 Fake stream 行为，不代替真实模型验证。

## 复现命令

在网络可访问 PyPI 与 Hugging Face、且 uv 能准备 Python 3.12 的 Apple Silicon Mac 上运行：

```bash
uv run --project spikes/mlx-lm-text --python 3.12 python spikes/mlx-lm-text/run_text_generation.py
```

成功标准是脚本加载模型后输出非空的增量文本，并以 stderr JSON 记录生成指标。当前阶段尚不能据此宣称 P0-02 已通过。
