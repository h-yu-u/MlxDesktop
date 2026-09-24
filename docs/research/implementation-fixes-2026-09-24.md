# 2026-09-24 高优先级修复批次

基线提交：`52faf30e9685eb91df45e23ca5155d77cc01be5a`

## 已处理

- 补齐 Naive UI `NDialogProvider`。
- 发送失败或生成中误按 Enter 时保留草稿和附件。
- 修复模型加载失败导致 Job 永久停留在非终态的问题。
- 让取消操作幂等，并确保取消优先于迟到的完成事件。
- 使用 `mlx-lm` sampler API；将 VLM 生成改为流式 API。
- 引入 Runtime 连接代际和失效清理，避免重启后继续使用旧端口与旧 Token。
- 将 SQLite 持久化拆分为聚焦的 Repository，并增加事务回滚和孤儿文件清理。
- 采用基于静态元数据与权重布局的稳定模型 ID，避免目录移动后产生新模型。
- 明确区分 Web 构建、Sidecar 构建和完整桌面应用构建。
- 增加 Python、Vue、API 客户端和 Rust CI 检查。

## 已验证

- Python 源码编译检查。
- 15 个新增/更新的 Python 回归测试。
- Python 文件 100 字符行宽检查。

## 当前环境未能执行

- pnpm/Vitest/Vue TypeScript 检查：当前执行环境无法访问 npm registry。
- Cargo fmt/clippy/Tauri 编译：当前执行环境未安装 Rust 工具链。
- Apple Silicon 真实 MLX、VLM、MFLUX 和 Sidecar 验收。

上述项目已加入 CI 或真机验收清单，不应被描述为已通过。
