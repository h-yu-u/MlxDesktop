# 架构

[文档入口](./README.md) · [工程规范](./engineering.md) · [验收状态](./status.md)

## 产品边界与已采纳决策

第一版面向 Apple Silicon macOS，主线为本地模型导入/下载、流式聊天、取消与历史、模型切换、文生图和作品参数复用。图片理解及正式分发的实际验收范围单独维护。

| 决策 | 目的 |
|---|---|
| Tauri 2 桌面壳 | 管理本地进程、原生交互和应用交付，Rust 保持精简 |
| Vue 3 + Vite + TypeScript + Naive UI + Pinia | 统一界面、类型、主题与交互状态，复用基础控件 |
| Python 3.12 + uv + FastAPI | 集成 MLX 生态，并由 Supervisor 统一产品协议 |
| 直接封装 mlx-lm、mlx-vlm、MFLUX 的 Python API | 隔离上游变更，不直接依赖上游 Server 作为产品服务 |
| 单活推理 Worker | 同时只持有一个大型模型，隔离崩溃，以进程退出兜底释放内存 |
| HTTP + SSE，进程间 NDJSON | 请求响应、增量事件和推理进程协议分开处理 |
| SQLite 元数据 + 本地文件 | 会话和索引可查询，附件与生成图片不作为大 BLOB 存入数据库 |

不进入第一版主线：跨平台推理、训练/量化平台、多用户与云同步、局域网公开服务、复杂 Agent/节点工作流、任意 Python 插件和多个大型模型同时常驻。对外兼容 API 仍属待完成能力。

## 进程与代码职责

```text
Vue UI ──Tauri Commands──> Tauri Shell ──启停──> Runtime Supervisor
   └──────────HTTP / SSE───────────────────────> │
                                               ├─ SQLite / 媒体文件
                                               ├─ 模型扫描 / HF 下载
                                               └─ NDJSON ─> 单活 Worker
                                                              └─ Engine Adapter
```

- **Vue UI**：页面与交互状态；通过 API 客户端调用 Runtime，通过桌面桥接取得连接信息，不直接读数据库或调用模型库。
- **Tauri Shell**：应用生命周期、固定 Runtime 的启动/停止/重启、一次性 Token、原生能力和最小权限；不承载聊天或模型业务。
- **Runtime Supervisor**：API、会话、模型、任务、事件、下载、数据库和文件；不直接持有大型模型。
- **Worker / Adapter**：加载模型、构造上游输入、流式推理、进度、取消、卸载和错误归一化；MLX 依赖仅在此边界加载。

前端源码位于 [apps/desktop/src](../apps/desktop/src)，Runtime 位于 [services/runtime/src/mlx_studio_runtime](../services/runtime/src/mlx_studio_runtime)，生成的跨端 DTO 位于 [packages/api-client](../packages/api-client)。依赖方向和组件职责见工程规范。

前端由 `app/composition-root.ts` 装配工作区；Pinia 入口仅暴露已配置的 controller。`application` 定义用例与端口，`presentation` 管理展示状态和视图生命周期，`infrastructure` 绑定类型化端点。跨工作区的模型目录、Runtime、任务观察和媒体缓存归属 `capabilities`，目录对消费者只读；Tauri、目录选择和导出归属 `platform`。展示组件只通过 props/events 交互。

Runtime 的 `composition_root.py` 构造 Repository、文件和 Worker 适配器。ChatService 与 ImageGenerationService 依赖窄端口；JobScheduler 统一串行租约、排队、取消及故障终态，ModelRuntime 管理驻留模型，RuntimeControl 编排加载/卸载/重启。HTTP 路由只做协议适配。旧 RuntimeService 和 SQLite CRUD 转发 Facade 已删除。具体决策见 [ADR 0001](./adr/0001-runtime-boundaries.md)，迁移与验证见[本次重构记录](./refactor-2026-10-15.md)。

## 通信与生命周期

桌面壳生成一次性 Session Token，通过进程环境交给 Runtime。Runtime 绑定 `127.0.0.1` 随机端口，就绪后输出包含端口、PID 和 `protocol_version` 的握手帧；Token 不写入磁盘或握手内容。前端通过带认证的 API 客户端访问业务接口，连接代际变化时清理旧客户端和连接信息。

内部 API 前缀为 `/internal/v1`，包括 Runtime 状态/诊断/重启、模型目录与管理、附件、会话、任务和事件。聊天使用 SSE 接收增量结果，图片创作通过任务接口查询状态；`/image-artifacts` 提供分页历史和经认证的 PNG 读取。HTTP 契约以 [FastAPI 入口](../services/runtime/src/mlx_studio_runtime/entrypoints/http/app.py) 及其 OpenAPI 为准，更新后运行 `pnpm api:generate`。

RuntimeSession 以 epoch 隔离旧连接回调；JobObserver 按 Job 分发并去重事件，缺口触发快照同步。离开页面只释放观察/轮询和 Object URL，不等于取消后台任务；返回聊天页面通过任务快照恢复。主动 AbortSignal 不使当前连接失效。

Supervisor 与 Worker 使用版本化 NDJSON：命令包含 ID、类型和 payload，事件包含递增 `seq`、类型和 payload，生成事件关联 `job_id`。stdout 专用于协议，诊断写 stderr；非法消息或版本不符按 Worker 故障处理。

任务生命周期：

```text
queued → preparing → running → succeeded
queued / preparing / running → cancelling → cancelled
非终态 → failed
```

取消应幂等，迟到的完成事件不能覆盖取消；模型加载或推理失败必须进入终态。先协作取消，必要时终止 Worker。Runtime 重启后未完成任务标记为中断失败，已完成历史保留；参数可以复用，不能将其描述为推理断点续算。

## 模型能力与调度

模型行为由 `ModelManifest`、静态配置/权重结构与兼容性数据驱动，显示名称仅用于展示。区分未知、部分支持、不兼容和损坏；扫描不执行模型代码，`trust_remote_code` 默认关闭。

聊天与图片共用单活 Worker 和推理锁，图片任务排队执行。切换模型时释放上一模型并加载目标模型。HF 目录查询和下载在 Supervisor 边界运行，不进入推理 Worker；下载成功和静态识别均不能代替真实模型验证。

## 存储、安全与恢复

SQLite 保存会话文本、模型登记、任务和作品参数；附件、PNG 等二进制写入媒体目录。数据库写入需事务保护，文件保存失败或数据库落库失败需补偿清理；文件读取校验目录约束、类型和大小。作品读取通过认证接口完成。

提交请求使用持久化编号去重；用户消息/任务与结果/终态分别属于一个用例事务。重新生成沿用轮次的附件与参数，成功前保留旧结果。迁移采用增量表/索引，旧模型 ID 与会话引用保留。安装身份与制品元数据分开；物理删除要求明确托管所有权，受活跃、排队及同路径登记保护，并先卸载 Worker。启动时将孤立的受管理媒体文件隔离到 `.recovery`，不静默清空用户数据。

Runtime 仅监听回环地址。内部 Session Token 临时有效；外部 API 默认关闭，启用时要求独立 Token。当前兼容聊天接口仍返回 501，不能作为完整 OpenAI 兼容服务使用。

模型扫描、附件上传、Markdown 渲染和文件导出均需遵循工程规范中的安全约束。日志默认不记录完整提示词、模型输出、文件内容或凭据；诊断信息需要脱敏。确定性内存释放依靠 Worker 退出，实际 RSS、长时间运行和打包后的清理行为仍需专项验收。
