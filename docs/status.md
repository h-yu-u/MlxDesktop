# 验收状态与后续工作

[文档入口](./README.md) · [使用说明](./getting-started.md) · [架构](./architecture.md)

本文根据当前实现与 2026-10-15 的本地验收结果整理。功能实现、FakeEngine 自动化和真实模型验证分别看待，不将单机结果扩展为全模型或正式发布结论。

## 已有实现

| 模块 | 当前范围 |
|---|---|
| 桌面与 Runtime | 启停/重启、认证握手、连接代际与失效清理、状态和诊断接口 |
| 任务与持久化 | 唯一终态、幂等取消、重启中断标记、SQLite 事务与文件补偿清理 |
| 聊天 | 模型选择、HTTP/SSE、停止生成、多轮上下文、会话持久化、失败保留草稿/附件 |
| 模型库 | 静态扫描/导入、能力识别、加载/卸载、登记与文件删除分离、HF MLX 下拉搜索/下载/自动登记 |
| 图片创作 | 模型与参数选择、排队/进度/取消、最近任务、PNG/参数保存、分页历史、预览/导出/复用 |
| 引擎 | Fake Text/Image 开发路径、mlx-lm / mlx-vlm Worker、可选 MFLUX 适配器 |
| 工具链 | 前端/Runtime/边界检查、测试、API 类型生成、Web 与 Sidecar/桌面构建脚本、CI 配置 |

## 真实模型验证

已记录的设备为 Apple M5 Pro / 64 GB，MLX 0.32.1，JIT 关闭。

| 模型 | 环境与已通过范围 | 尚不能推定 |
|---|---|---|
| `orcarouter/Qwen3.8-27B-Uncensored-MLX`，`4-bit` 子目录 | mlx-vlm 0.6.14；文本流式回复、多轮上下文、SQLite 持久化、取消、Worker 重启 | 图片理解、长上下文、长期稳定性、其他模型 |
| Qwen Image 2.1 原生 MFLUX BF16 导出 | MFLUX 0.22.0，缓存上限 4 GiB；512×512、12 steps、Seed 42；文生图、进度、取消后再生成、PNG/参数保存、Runtime 重启后历史、聊天→生图→继续原对话 | 图片编辑、LoRA、高分辨率、其他导出/模型或设备 |

当前 Worker 显式关闭思考输出和 MLX JIT，作为已验证环境的配置；不将此结论推广到其他版本。

Qwen2.5-0.5B（mlx-lm）、Qwen2-VL-2B 图片理解、Z-Image-Turbo 仍为候选未验证模型。FLUX/Qwen Image 其他适配分支的存在也不代表真机验收通过。

## 复验命令

以下命令在仓库根目录、具有完整本地模型的 Apple Silicon Mac 上执行。脚本使用临时数据库并在结束时关闭测试 Runtime，不操作正式会话数据。

真实聊天：

```bash
uv run --frozen --project services/runtime --extra mlx-vlm --python 3.12 \
  python scripts/verify_local_chat.py --model-path /path/to/Qwen3.8-27B-Uncensored-MLX/4-bit
```

真实图片及聊天/生图切换：

```bash
uv run --frozen --project services/runtime --extra mlx-vlm --extra mflux --python 3.12 \
  python scripts/verify_local_image.py --model-path /path/to/qwen-image-2.1-mlx-bf16 \
  --output /tmp/mlx-studio-qwen-image.png \
  --chat-model-path /path/to/Qwen3.8-27B-Uncensored-MLX/4-bit
```

只验证图片时可省略 `--chat-model-path`。输出路径会保存验收 PNG。

系统与早期独立探针保留为辅助工具，脚本能执行不代表对应模型已经通过：

```bash
python3 scripts/system_probe.py
uv run --project spikes/mlx-lm-text --python 3.12 python spikes/mlx-lm-text/run_text_generation.py
uv run --project spikes/mlx-vlm-image --python 3.12 python spikes/mlx-vlm-image/run_vlm.py --image /path/to/image.png
uv run --project spikes/mflux-image --python 3.12 python spikes/mflux-image/run_image_generation.py
```

文本探针默认固定小模型 revision，输出增量文本与耗时/吞吐/内存摘要。VLM 探针输入图片上限 50 MB。MFLUX 探针默认检查 PNG 后清理临时文件，指定 `--output` 才保留；其候选模型与当前已验证 Qwen Image 不同。独立 Spike 的依赖和上游 API 需单独复验，不能代替产品 Runtime 测试。

系统探针只读硬件、系统、Python 和磁盘，不安装依赖或访问网络。输出仅表示采集时环境，不是最低配置承诺。

## 后续工作与发布条件

| 方向 | 剩余工作及验收要求 |
|---|---|
| 模型与下载 | 扩展真实架构/量化矩阵；完善下载进度、跨重启恢复及磁盘压力处理 |
| 多模态 | 真实图片理解与连续追问、多图/像素解码限制；音视频能力后续评估 |
| 图片创作 | 其他模型/导出、高分辨率和编辑分别验收；批量、LoRA 等扩展单独确定范围 |
| 稳定性 | 真模型故障注入、自动退避恢复、长时间运行、连续切换/取消与 Worker RSS 回收对照 |
| 性能与安全 | 固定设备/模型/参数的 TTFT、吞吐、内存与生图基线；路径/超大附件/Markdown/日志隐私及诊断导出验收 |
| 外部 API | 当前默认关闭；兼容聊天接口返回 501，协议、流式响应和独立认证需完成后再开放 |
| 桌面交付 | PyInstaller/MLX 动态库打包、退出清理、嵌套签名、公证、更新/回滚、数据迁移、首次启动引导 |

正式发布仍需执行 `pnpm build:app`，并在无开发工具/Python 的干净 Apple Silicon Mac 上验证安装、Sidecar、离线使用、历史保留、退出清理和 Gatekeeper。至少覆盖两种内存规格，升级失败时旧版本可启动、会话/模型登记/作品完整，卸载不得默认删除外部模型目录。

质量检查通过、Web 构建成功或某个本地模型通过，均不能代替这些发布条件。后续验收结果直接更新本文件，不再累积旧 P0–P9 阶段状态或临时修复日报。
