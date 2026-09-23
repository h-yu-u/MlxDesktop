# MLX Studio

Apple Silicon 本地 AI 工作台。桌面端为 Tauri 2 + Vue 3；本地 Runtime 为 FastAPI Supervisor + 单活 NDJSON Worker。当前实现包含 FakeEngine 端到端路径、会话 SQLite 持久化、模型静态扫描和聊天 UI；MLX/VLM/MFLUX 与正式分发仍需真实硬件验证。

## 环境

- Apple Silicon Mac；macOS。
- Node.js 22（仓库提供 `.nvmrc`），pnpm 11。
- Rust stable 1.77.2 或更高版本，并安装 macOS command line tools。
- uv 和 Python 3.12。
- 真实 MLX 模型需要网络下载对应依赖和模型文件。

## 初始化和运行

```bash
nvm use
pnpm bootstrap
pnpm dev
```

`pnpm dev` 启动 Tauri 桌面端。Debug 模式由固定的 `uv run` 命令启动 Runtime，Release 模式使用打包的 Runtime Sidecar。仅调试浏览器 UI 时可运行 `pnpm dev:web`；浏览器模式需要通过 `VITE_RUNTIME_URL` 和 `VITE_RUNTIME_TOKEN` 连接单独启动的本地 Runtime。

桌面侧生成一次性 Session Token 并通过环境变量传给 Runtime。Runtime 绑定 `127.0.0.1` 的随机端口，通过 stdout 单行 handshake 返回端口、PID 和协议版本；Token 不写入磁盘，也不出现在 handshake 中。

## 检查

```bash
pnpm check
pnpm test
pnpm build:runtime
pnpm build:desktop
```

`pnpm api:generate` 从 Runtime 的 FastAPI schema 生成 API 类型，无需启动监听端口。桌面调试模式会自动启动 Runtime；手动启动时运行 `uv run --project services/runtime --python 3.12 python -m mlx_studio_runtime.entrypoints.http.main`，并设置 `PYTHONPATH=services/runtime/src`。

## 模块

```text
apps/desktop/       Tauri shell、Vue UI、feature modules
services/runtime/   FastAPI Supervisor、domain、SQLite、Worker IPC
packages/api-client/Authenticated HTTP/SSE client and generated OpenAPI types
compatibility/      Candidate compatibility matrix (not yet verified)
spikes/             P0 feasibility spikes
docs/adr/           Accepted architecture decisions
```

运行时 API 使用稳定错误码，事件采用带递增序号的 JSON SSE。外部 OpenAI 风格 API 默认关闭，启用时必须配置独立 token。

## 当前边界

`Fake Text Engine (Development)` 不需要 MLX，适合开发聊天、SSE、取消、SQLite 恢复和 Worker 重启。文本真实推理 Spike 在 `spikes/mlx-lm-text/`；图片理解已经接入附件存储和 `mlx-vlm` Worker 路由，但尚无真实模型验证。MFLUX、生图队列、签名、公证和更新通道仍未完成。真实模型基线、两小时/八小时 soak、干净机器 Sidecar 均不得以 FakeEngine 结果替代。阶段验收状态见 `docs/research/p1-p9-delivery-status.md`。
