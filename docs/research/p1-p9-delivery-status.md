# P1–P9 实现与验收状态

本文件区分代码已落地与真实硬件/分发验收。只有自动化检查或真实环境验收通过时，才把对应项标为“已验证”。

| 阶段 | 实现 | 验收状态 | 主要未完成项 |
|---|---|---|---|
| P0 可行性 | 系统探针、文本/VLM/MFLUX spikes、NDJSON Worker、候选兼容清单 | FakeEngine 和系统探针通过；真实 MLX 未验证 | MLX wheel、真实模型下载与推理、真实 RSS、模型兼容矩阵 |
| P1 工程骨架 | pnpm workspace、Vue/Tauri、Python 3.12 Runtime、ADR、质量命令、OpenAPI 类型生成 | 前端构建、边界检查、Runtime Ruff/Pyright、schema 生成通过 | 本机没有 Cargo；Tauri 原生编译尚未验证 |
| P2 Runtime | FastAPI Supervisor、bearer 会话认证、SQLite、模型扫描、单 Worker 串行任务、事件流 | FakeEngine API/Worker/SQLite 自动化用例通过；真实 Runtime 回环启动握手通过 | 重启后排队任务恢复、迁移备份恢复和故障注入 |
| P3 桌面生命周期 | Tauri sidecar 启动、临时 Token、回环随机端口握手、退出时结束子进程 | Runtime handshake 与健康接口已实测 | Rust 编译、Sidecar 打包、崩溃自动恢复 |
| P4 文本聊天 | SSE、停止、持久会话、上下文历史、重新生成、Markdown 清理 | FakeEngine 集成和前端用例通过 | mlx-lm 真实模型的 token 流和取消实测 |
| P5 模型管理 | 本地目录导入、静态元数据扫描、Hugging Face 下载/界面、加载/卸载/移除、受控文件删除 | API 和界面已接入 | 下载进度/恢复、Keychain Token、多个真实架构验证 |
| P6 多模态 | 图片格式/大小限制、SHA-256、附件元数据与消息关联、manifest 驱动单图入口、mlx-vlm Worker 路由 | FakeEngine 拒绝非法图片请求和附件存储已测 | 真实 VLM、图片缓存/缩略图、视觉 token 流和历史图片上下文 |
| P7 Image Studio | 参数面板和独立页面 | 未完成 | MFLUX Worker、任务状态机/队列、取消、图片 Artifact、历史画廊与真实生成 |
| P8 稳定性与安全 | 运行指标、脱敏诊断 ZIP、模型路径删除限制、依赖边界、Fake Worker 10 轮重启 | 自动化测试和静态检查通过 | Soak/真实模型回归、故障注入、兼容矩阵自动执行、附件孤儿清理、外部 API 完整兼容 |
| P9 发布 | Apple Silicon Runtime sidecar 构建脚本、DMG/app Tauri bundle 目标 | 未完成 | sidecar 构建、签名、公证、更新通道、干净 Mac 安装和升级回滚演练 |

## 当前验收命令结果

- `pnpm check:frontend`：通过。
- `pnpm check:boundaries`：通过。
- `pnpm build:desktop`：通过。
- `pnpm test:frontend`：3 个用例通过。
- Python 3.12 Runtime Ruff 与严格 Pyright：通过。
- Python 3.12 unittest：16 个用例通过（含 API、Fake Worker 生命周期和系统探针）。
- Sidecar、真实 MLX 推理、MFLUX 生图、Rust/Tauri 构建：未运行或未通过真实环境验收；不得作为发布通过条件。
