# P1–P9 实现与验收状态

本文件区分代码已落地与真实硬件/分发验收。

| 阶段 | 已实现 | 尚未完成 |
|---|---|---|
| P1 工程骨架 | GitHub Actions、前端/Runtime/Rust 检查命令、构建语义拆分 | 合并后的真实 CI 结果 |
| P2 Runtime | Job 终态保护、SQLite 事务、重启任务恢复、模型状态持久化 | 真实模型故障注入与长时间运行 |
| P3 桌面生命周期 | 多等待者 readiness、连接代际、失效清理、手动进程重启 | Sidecar 真机构建、自动退避重启 |
| P4 文本聊天 | 失败保留草稿、SSE 解析增强、取消竞态修复、mlx-lm sampler | 真实模型 token 流和取消实测 |
| P5 模型管理 | 更稳定的模型 ID、静态能力识别、模型状态落库 | 下载进度/恢复和真实架构矩阵 |
| P6 多模态 | mlx-vlm 流式 Worker 路由 | 真实 VLM、像素解码上限和视觉缓存 |
| P7 Image Studio | 参数页面 | MFLUX Worker、队列、Artifact 和画廊 |
| P8 稳定性与安全 | 事务回滚、孤儿附件清理、回归测试、CI | Soak、完整兼容矩阵、外部 API |
| P9 发布 | 完整构建命令和 Sidecar 脚本 | 签名、公证、更新通道和干净 Mac 验收 |

完整桌面发布构建只允许在 Apple Silicon macOS 运行：

```bash
pnpm build:app
```
