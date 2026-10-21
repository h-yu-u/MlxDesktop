# 交互一致性与共享 UI

[文档入口](./README.md) · [工程规范](./engineering.md) · [架构](./architecture.md)

本轮实现依据 2026-10-20 的《MlxDesktop 交互一致性、公共组件与 UX 设计技术方案》，保留现有 Vue、Naive UI、Pinia、Runtime 与 Coding Host 的业务边界。没有新增依赖、数据库迁移、内部 RPC 变更或默认工具授权迁移。

## 操作结果与草稿

- `platform/files.ts` 返回明确的保存、下载发起、取消或失败结果。Chat、Image、Audio 和 Runtime 导出均等待实际结果；读取期间离开页面不会打开迟到的保存窗口，已发生的保存结果不会被改写。每个来源分别记录导出状态。
- Coding 和工具助手使用 `shared/lib/scoped-text-drafts.ts`，按项目／会话隔离文本，以草稿 ID 和 revision 决定是否消费。文本改成其他内容再改回来，也不会被旧响应清空。Chat 原有附件草稿与引用生命周期保留。
- Coding 提交返回实际 run，任务已接纳后的快照失败单独提示。steer 的未知结果先同步状态，不自动重放。工具助手的未知提交票据随 app 生命周期保留，恢复时重用原会话、请求和 submissionId；starting 快照不代替公开提交确认。
- 文字助手生成候选结果，应用时检查打开助手后的目标版本。目标已变更时提供替换、复制或取消，生成期间不允许编辑候选框。

这些草稿仅在当前 app 进程中保留，不承诺跨启动恢复，不写入 localStorage。

## 设置、默认值与音色

Web Search 和 Coding 设置将编辑草稿与已保存值分开；失败保留输入，放弃修改恢复已保存基线。Web Search 只测试已保存的 configId／revision，dirty 时显示先保存的原因。测试响应保留 `ok`、`elapsedMs`，历史验证标记与当前失败分开显示。

MCP 编辑器区分未保存、提交未知、已保存待回读及保存完成后的列表刷新失败。未知提交保留 mutationId；已有回执时只重读配置。字段及凭据编辑草稿保存在当前 app 的内存中，关闭抽屉或返回设置仍可继续。保存中不能切换到另一份配置；错误显示在抽屉内。连接测试记录对应服务及被测配置版本。

默认选择继续使用现有 workspace／project／`agent-default` scope。明确的空绑定不继续继承；读取失败不能保存空默认值；绑定写入由调用者提供 mutationId。界面准确标为工作区、项目或工具助手默认。

音色修改等待 PATCH 成功后才退出编辑。克隆创作可进入音色库“保存并用于当前草稿”：只回填 voiceId，保留朗读文字，不自动生成。换模式、换音色、离开流程或离页后的迟到结果不强制回跳，创建成功的音色仍进入目录。

## 媒体作品与恢复

新增两个经认证、带 response_model 的只读接口：

- `GET /internal/v1/image-artifacts/{id}`
- `GET /internal/v1/audio-artifacts/{id}`

它们复用现有仓库与 DTO，不要求作品位于历史第一页。列表、详情和文件错误分别管理；缺少媒体文件不妨碍元数据读取。刷新不会抢走用户选中的作品，分页 offset 根据原始页长度推进。音频删除成功后按 ID 清理，删除 A 的迟到结果不影响正在查看的 B。

恢复图片／语音参数会报告缺失模型、引用、遮罩、语言、speaker 或音色版本差异，不静默选择其他资源。恢复期间若编辑了当前草稿，返回结果保留为候选。引用编号与原文保留；替换原图会清除旧遮罩绑定。

能力选择器通过媒体公共入口浏览图片作品、上传参考图或选择音色。作品经读取及上传后才成为 attachment，关闭选择器、切换目标或重复确认不会迟到回填。只预览当前选择的资源，不为初始列表下载所有原图，也不提供不存在的全局附件搜索。

## 共享组件与布局

`shared/ui` 提供 ComposerShell、SessionListItem、MarkdownContent、TaskStatusPanel、FormActionBar、ResourceListState 和 PageHeader；模型能力提供 ModelSelect。每个主要抽象均接入真实业务场景，领域提交、审批、附件与媒体操作仍由各自容器管理。会话重命名继续使用现有弹窗，输入区的快捷键差异保留为明确的 Chat / Coding 规则。

MarkdownContent 复用原安全渲染器与约 100 ms 流式节流，终稿立即刷新。复制意图包含内容、代码块与请求身份；内容替换或代码变化会清理旧反馈。Clipboard 仍由平台边界处理。

设置采用 `/settings` 父布局，旧 Skills / MCP / builtin URL 保持可用并传入准确的 tab。联网搜索只有内置工具页一份完整表单；概览只提供摘要。Chat 顶部保留运行状态和模型设置入口；模型库优先展示本地模型，发现入口按需打开；已加载模型提供卸载。

主题唯一手写来源为 `shared/styles/theme.tokens.json`。`pnpm tokens:generate` 生成 CSS／TS，Naive UI 与产品 CSS 使用同源值；`pnpm tokens:check` 纳入 `pnpm check`。修改 token 后需重新生成，不手改生成文件。

## 验证与边界（2026-10-21）

自动化验证包括：

- `pnpm check`：格式、类型、lint、Python、Coding、依赖边界和源码长度检查。
- `pnpm test`：前端 222 项、Runtime 168 项、Coding Host 46 项、验收工具 8 项。
- `pnpm build:web`：构建通过；存在超过 500 kB 的 chunk 提示，本轮未做打包体积优化。
- `pnpm api:generate`、`pnpm tokens:check`：API 重新生成字节稳定，主题无漂移。

回归覆盖导出取消和大小边界、草稿隔离及乱序响应、已接纳后同步失败、Agent 未知提交恢复、MCP 回执恢复及草稿保留、设置 dirty／测试版本、媒体深链、分页失败、删除与选择并发、恢复候选、资产准备关闭和重复确认等。

本地浏览器使用隔离临时数据库及 FakeEngine，已检查图片生成与结果显示、旧 MCP／内置工具入口、未保存联网草稿离开后返回及禁测提示。图片页面在 1440、1280、1024、820、520 px 视口均无横向页面溢出；截图保存在本机 `.build/ux-acceptance/image-<width>.png`，不纳入源码。

尚未验证：Tauri 原生保存对话框与取消后的焦点、WebView Clipboard fallback、真实 MLX 文本／VLM／MFLUX／语音质量、hardened sidecar、签名公证及干净机器验收。浏览器与 FakeEngine 验证不代替这些证据。窗口截图也不代表所有业务状态、原生输入法和辅助技术均已完成人工验收。
