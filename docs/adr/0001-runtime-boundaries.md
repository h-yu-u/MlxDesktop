# ADR 0001：用例、资源租约与边界契约

日期：2026-10-15。基线：`cff5d71792580428d7813ced2ffec7da3e115dac`。

## 决策

保持 Vue 3 / Pinia / Naive UI / Tauri / Python / MLX 的技术路线，使用显式依赖组合，不引入依赖注入框架或插件发现系统。

- 前端组合根注册工作区工厂。Pinia 入口只绑定控制器，不创建 HTTP、SSE、轮询、Object URL 或原生对话框。控制器依赖应用端口；具体端点适配器由组合根注入。
- 模型目录只有一个查询投影所有者，对功能模块提供只读视图。聊天与生图各自保留模型选择和草稿。Runtime 概况也只有一个查询入口。
- RuntimeSession 拥有连接代际；JobObserver 拥有共享事件连接、游标、按 Job 分发、重连与快照恢复。页面释放观察者不取消后台任务，重新进入后恢复观察。
- JobScheduler 拥有队列、执行锁、任务取消及终态收敛。最多一个推理租约；停止资源失败时阻止继续接纳，明确要求恢复。ModelRuntime 独占 Worker 与模型驻留状态。
- ChatService、ImageGenerationService 依赖窄端口，不能获取整个 RuntimeApplication。组合根负责具体 Repository、文件、Worker、系统信息的创建。
- 领域层不扫描文件、不引入 HTTP / Vue / SQLite / MLX。扫描、协议解码、附件/图片文件、下载及诊断分别由适配器承担。
- 消息与 Job 接纳、完成结果与 Job 终态使用用例事务。提交成功后更新内存并发布事件。SQLite 之外的文件采用暂存、补偿和启动隔离恢复，不声称文件与数据库组成分布式事务。
- 请求编号分别保护聊天与生图提交。相同编号和相同输入返回已存在的任务；不同输入复用编号返回冲突。取消和重复终态保持幂等。
- 模型 ID 表示安装/登记，而非权重内容哈希。新安装使用规范路径、来源和修订派生身份；同路径旧登记保留旧 ID。制品信息明确标注元数据指纹层级，不把它当成权重内容摘要。
- 删除托管文件必须具有明确安装所有权、目录校验和资源保护。导入目录只移除登记；相同目录的别名登记与任务引用也受保护。

## 资源生命周期

每项异步资源有 owner、释放操作与晚到结果规则。RuntimeSession 使用 epoch；会话读取使用请求代际和 AbortSignal；JobObserver 按实例及序列恢复；媒体下载有 AbortSignal、有限缓存和 URL 回收；Worker 在 Supervisor 输入管道关闭后退出。

Rust 的连接与错误放在同一代际快照中，重启与退出串行协调。握手缓冲有上限，端口和协议版本明确校验。

桌面壳拥有 Runtime stdin 写端。显式启用父管道监听时，EOF 触发 Supervisor 生命周期清理；不能只杀 onefile bootloader 并假定内部 Python 进程同时退出。冻结入口调用 multiprocessing.freeze_support，辅助进程不会复用 HTTP 入口并触碰同一数据库。

## 可执行约束

`pnpm check` 包含格式、类型、lint、Python/TypeScript/Vue AST 依赖图、循环依赖、生产源码长度和公共样式归属检查。检查器有故意违规的 fixture。展示组件不能依赖 Store、HTTP 或 Tauri；跨功能模块不能穿透内部路径；下层不能反向引用组合根。

查询 ReadModel 可以复用生成的契约类型；有业务规则的领域模型保持独立，避免机械复制 DTO。控制器工厂包含多个小动作，其外层闭包是状态装配范围，不以机械移动目录或拆成万能 Context 作为验收。

## 交付边界

FakeEngine、源码真实模型、打包后真实模型、Developer ID 签名、公证、干净机器验收分别记录。普通 CI、占位 Sidecar、单机模型成功都不能替代正式发布验收。具体结果见 `docs/refactor-2026-10-15.md`。
