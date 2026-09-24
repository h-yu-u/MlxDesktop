# MLX Studio

Apple Silicon 本地 AI 工作台。桌面端为 Tauri 2 + Vue 3；本地 Runtime 为 FastAPI Supervisor + 单活 NDJSON Worker。当前实现包含 FakeEngine 端到端路径、会话 SQLite 持久化、模型静态扫描、聊天 UI、Runtime 连接失效恢复和任务终态保护；真实 MLX/VLM/MFLUX 与正式分发仍需 Apple Silicon 真机验证。

## 环境

- Apple Silicon Mac；macOS。
- Node.js 22（仓库提供 `.nvmrc`），pnpm 11。
- Rust stable 1.77.2 或更高版本，并安装 macOS command line tools。
- uv 和 Python 3.12。

## 初始化和运行

```bash
nvm use
pnpm bootstrap
pnpm dev
```

桌面侧生成一次性 Session Token 并传给 Runtime。Runtime 仅绑定 `127.0.0.1` 随机端口，通过 stdout 握手返回端口、PID 和协议版本；Token 不写入磁盘。连接失效后前端会清理旧客户端，并可由桌面壳重新启动 Runtime。

## 检查与构建

```bash
pnpm check
pnpm test
pnpm build:web
pnpm check:rust
```

Apple Silicon macOS 发布机上的完整应用构建：

```bash
pnpm build:app
```

`build:web` 只构建 Vue 前端；`build:app` 会依次构建 Web、PyInstaller Runtime Sidecar 和 Tauri `.app`/`.dmg`，两者不能作为同一项发布验收结果。

## 当前边界

`Fake Text Engine (Development)` 适合开发聊天、SSE、取消、SQLite 恢复和 Worker 重启。真实 `mlx-lm`、`mlx-vlm`、MFLUX、Sidecar、签名、公证和干净机器安装仍需 Apple Silicon 真机验收，不得由 FakeEngine 结果替代。
