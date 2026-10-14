# MLX Studio 文档

MLX Studio 是面向 Apple Silicon macOS 的本地 AI 工作台，包含模型管理、流式聊天、图片创作和本地历史记录。

## 阅读入口

| 文档 | 内容 |
|---|---|
| [使用与开发](./getting-started.md) | 环境准备、启动、模型下载、聊天、生图历史、常用命令 |
| [架构](./architecture.md) | 进程职责、通信、模型能力、任务生命周期、存储与安全决策 |
| [工程规范](./engineering.md) | 分层、编码约束、依赖、测试与完成标准 |
| [验收状态与后续工作](./status.md) | 已实现范围、真实模型验证、复验命令、待完成事项 |

## 事实来源与维护

- 开发命令以根目录 [package.json](../package.json) 为准。
- 模型验证环境、已通过场景和未验证范围统一维护在[验收状态](./status.md)。
- HTTP DTO 以 FastAPI OpenAPI 为准，生成到 [API 客户端类型](../packages/api-client/src/generated-schema.d.ts)。
- AI 助手遵循根目录 [AGENTS.md](../AGENTS.md) 和其引用的工程规范。

项目 Markdown 除 `AGENTS.md` 外统一放在本目录。功能变化直接更新对应文档；一次性的排查过程、临时修复清单、旧环境安装失败记录不另建长期文档。新增架构决策先补充架构文档；已实施功能与计划、自动化检查与真机验收分别描述。
