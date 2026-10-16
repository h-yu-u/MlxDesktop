# 验收状态与后续工作

[文档入口](./README.md) · [使用说明](./getting-started.md) · [架构](./architecture.md)

本文根据当前实现与 2026-10-15 至 2026-10-16 的本地验收结果整理。功能实现、FakeEngine 自动化和真实模型验证分别看待，不将单机结果扩展为全模型或正式发布结论。

## 已有实现

| 模块 | 当前范围 |
|---|---|
| 桌面与 Runtime | 启停/重启、认证握手、连接代际与失效清理、状态和诊断接口 |
| 任务与持久化 | 唯一终态、幂等取消、重启中断标记、SQLite 事务与文件补偿清理 |
| 聊天 | 模型选择、HTTP/SSE、停止生成、多轮上下文、会话持久化、重命名/删除/置顶及取消置顶、失败保留草稿/附件 |
| Coding | 独立 Pi 工作区、项目与会话、三种模式、工具时间线、命令/测试修改审批、停止与补充、下一任务排队、按需文件/Diff、冲突撤销与验证证据、重启恢复 |
| 模型库 | 静态扫描/导入、能力识别、加载/卸载、登记与文件删除分离、HF MLX 下拉搜索/下载/自动登记 |
| 图片创作 | 文生图/图片编辑/局部重绘、参考图上传/排序、区域画笔与橡皮擦/撤销、原图对比、继续编辑、排队/进度/取消、PNG/参数/参考附件保存和历史复用 |
| 语音创作 | 预设合成/参考克隆、音色库与授权记录、音频校验、任务取消/恢复、作品历史/试听/波形/WAV 导出 |
| 引擎 | Fake Text/Image 开发路径、mlx-lm / mlx-vlm Worker、可选 MFLUX 适配器 |
| 工具链 | 前端/Runtime/边界检查、测试、API 类型生成、Web 与 Sidecar/桌面构建脚本、CI 配置 |

侧栏资源卡片显示实时系统内存（已用/总量）、使用率进度条、推理 Worker 当前占用和可用磁盘；设置页同步展示。每 2.5 秒后台采样，文档隐藏时暂停、重新可见时立即更新，后台采样不触发设置页加载遮罩。macOS 读取原生 VM/进程计数，不安装额外依赖：系统已用包含匿名页、不可分页页和实际压缩存储，排除文件缓存及可回收页；Worker 使用 physical footprint（含压缩内存），不称为专属显存或整个 App 占用。Linux 开发路径使用 MemAvailable 和 Worker RSS；采集不可用显示 `—`，未启动 Worker 显示“未启动”。旧峰值 RSS 字段仅为协议兼容保留。

实时指标更新已通过 `pnpm check`、前端 62 项和 Runtime 81 项测试、API 类型重复生成一致性与实际 App 构建。发布 Sidecar 验证系统总量/已用/可用一致、Worker 加载后占用大于零、卸载后归零；本机 64 MiB 映射申请/释放实验证明进程计数随当前占用升降。UI 已检查实时卡片、真实进度条、设置页同步及短窗口布局。证据位于忽略的 `.build/memory-validation/evidence.json`，App 内 Sidecar 与测试二进制哈希一致；没有新增依赖。

本次架构重构的阶段 0–8 实施、数据兼容策略及完整本机证据见[重构验收记录](./refactor-2026-10-15.md)。用户已确认正式签名、公证和干净机器验收另行执行。

## 真实模型验证

已记录的设备为 Apple M5 Pro / 64 GB，MLX 0.32.1，JIT 关闭。

| 模型 | 环境与已通过范围 | 尚不能推定 |
|---|---|---|
| `orcarouter/Qwen3.8-27B-Uncensored-MLX`，`4-bit` 子目录 | mlx-vlm 0.6.14；源码与实际 release Sidecar 的文本流式回复、多轮上下文、SQLite 持久化、取消、Worker 重启；测试 PNG 图片理解及保留附件/参数的重新生成 | 多图、长上下文、长期稳定性、其他模型 |
| Qwen Image 2.1 原生 MFLUX BF16 导出 | MFLUX 0.22.0，缓存上限 4 GiB；源码与实际 release Sidecar 的 512×512、12 steps、Seed 42；文生图、进度、取消后再生成、PNG/参数保存、Runtime 重启后历史、聊天→生图→继续原对话 | 图片编辑、LoRA、高分辨率、其他导出/模型或设备 |
| `OsaurusAI/Qwen-Image-2.1-mflux-8bit` 完整编辑导出 | MFLUX 0.22.0；模型级改色、中文换背景、双参考图、蒙版、提示词改写；源码真实 Runtime 的编辑取消/再生成、PNG 和参考顺序/蒙版保存、重启读取；浏览器实操双图编辑与画笔重绘，1440/1024/768 窗口布局与刷新恢复 | 十参考图、高分辨率、人物一致性、LoRA/ControlNet、长期运行、此次新增编辑功能的发布 Sidecar/原生打包交互 |

当前 Worker 显式关闭思考输出和 MLX JIT，作为已验证环境的配置；不将此结论推广到其他版本。

Qwen2.5-0.5B（mlx-lm）、Qwen2-VL-2B、Z-Image-Turbo 仍为候选未验证模型。FLUX/Qwen Image 其他适配分支的存在也不代表真机验收通过。

## 复验命令

图片编辑 UI 与真实接口的本机证据保存在忽略目录 `.build/validation/image-edit-integration/`。没有新增依赖；完整模型根据静态视觉组件识别能力，接口只接受已登记附件 ID，Worker 限制输入到受管附件目录并检查图像像素上限。

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

真实图片编辑（红茶壶基线原图、蓝色参考图与对应黑白蒙版；白色修改、黑色保留）：

```bash
uv run --frozen --project services/runtime --extra mlx-vlm --extra mflux --python 3.12 \
  python scripts/verify_local_edit.py --model-path /path/to/qwen-image-2.1-edit-mlx-8bit \
  --source /path/to/source.png --reference /path/to/reference.png \
  --mask /path/to/mask.png --output /tmp/mlx-edit-check
```

脚本用 512×512、40 步、Seed 42 测试编辑、双参考顺序、取消后重新生成、区域修改和重启后的图片/附件读取。该脚本专用于红茶壶与蓝色参考图的基线复验；自有素材应按修改需求调整脚本中的测试指令。参考图与蒙版必须对应原图。

真实图片理解和重新生成：

```bash
uv run --frozen --project services/runtime --extra mlx-vlm --python 3.12 \
  python scripts/verify_local_vision.py --model-path /path/to/Qwen3.8-27B-Uncensored-MLX/4-bit \
  --image /path/to/verification.png
```

上述三个脚本均接受 `--sidecar /path/to/mlx-studio-runtime`，此时从实际二进制启动，并清除开发源码 PYTHONPATH。`scripts/verify_packaged_runtime.py --sidecar ...` 验证同一包的 FakeEngine、诊断、取消与重启持久化；不能单独代替真实引擎验证。

`scripts/verify_desktop_shutdown.py --sidecar ...` 模拟桌面壳强制停止 onefile bootloader，并关闭它持有的 stdin 管道；已验证内部 Runtime 和已加载 Worker 全部退出。冻结入口同时处理 multiprocessing 辅助进程，避免误启动额外 Runtime。最终 `.app` 已本机构建，签名、公证、原生 GUI 的正式安装与干净机器验收另行执行。

系统与早期独立探针保留为辅助工具，脚本能执行不代表对应模型已经通过：

```bash
python3 scripts/system_probe.py
uv run --project spikes/mlx-lm-text --python 3.12 python spikes/mlx-lm-text/run_text_generation.py
uv run --project spikes/mlx-vlm-image --python 3.12 python spikes/mlx-vlm-image/run_vlm.py --image /path/to/image.png
uv run --project spikes/mflux-image --python 3.12 python spikes/mflux-image/run_image_generation.py
```

文本探针默认固定小模型 revision，输出增量文本与耗时/吞吐/内存摘要。VLM 探针输入图片上限 50 MB。MFLUX 探针默认检查 PNG 后清理临时文件，指定 `--output` 才保留；其候选模型与当前已验证 Qwen Image 不同。独立 Spike 的依赖和上游 API 需单独复验，不能代替产品 Runtime 测试。

系统探针只读硬件、系统、Python 和磁盘，不安装依赖或访问网络。输出仅表示采集时环境，不是最低配置承诺。

## 聊天流式输出专项复验（2026-10-15）

已确认本机最近一条提前结束的回答恰好生成 512 token，达到旧默认上限。默认输出上限已提高到 4096，设置允许 8192；Worker 的 `finish_reason` 与生成 token 数传递到任务完成事件和会话参数，页面区分长度截断并提供「继续回答」。

对于 MLX-VLM 的 ByteLevel BPE 解码器，已改为按完整 UTF-8 字符输出，避免中文等待空格；其他解码器保留原行为。前端合并密集增量、限制 Markdown 解析频率、缓存未变化消息，并在实际 DOM 更新后按帧跟随滚动，向上阅读时暂停跟随。

本机 Apple M5 Pro / 64 GB、同一本地 Qwen 4-bit 模型、同一确定性测试输入：两次均生成 942 token 并自然结束；分片中位间隔从 339.06 ms 降至 56.60 ms，最大间隔从 411.77 ms 降至 61.13 ms，生成总耗时基本相同（53.33 / 53.36 秒）。这是显示分片粒度改善，不代表推理吞吐增加。中文、英文空格、Markdown 代码、表情及特殊 token 的最终解码与原解码器和分词器一致。

真实 HTTP/SSE 验证覆盖旧上限之外的长回答、16-token 截断原因、持久化一致性、主动断流后的游标重放、取消和正常退出。

独立浏览器使用 FakeEngine 的密集长文本验证页面渲染：跟随滚动和向上阅读保持通过，最终文本尾部完整，无页面异常及横向溢出；该次采样未记录超过 50 ms 的主线程任务。该浏览器验证使用临时数据，真实模型的输出与恢复另由上述 API 验证覆盖。

复验命令：

```bash
uv run --frozen --project services/runtime --extra mlx-vlm --python 3.12 \
  python scripts/verify_chat_streaming.py \
  --model-path /path/to/Qwen3.8-27B-Uncensored-MLX/4-bit \
  --output /tmp/mlx-chat-streaming.json
```

本次未重新打包 Sidecar，也未做长时间压力测试；开发应用需重启 Runtime 后使用新的解码器和完成原因。

## Coding 接入验收（2026-10-16）

已接入 Pi / pi-ai 1.2.0、TypeBox 1.3.27、内置 Node 22.23.1。Node Host 单独管理 Coding 元数据与 Pi 会话；新增内部结构化推理 API，按单次请求取得现有 MLX 推理租约。模型工具能力需经过实际闭环验证，关联引擎、模板/配置与权重版本信息；失败保持未验证。完整使用、协议范围和权限边界见 [Coding](./coding.md)。

本次通过的验证：

| 验证 | 结果与证据范围 |
|---|---|
| `pnpm check` | Prettier、Vue/TypeScript、ESLint、Ruff/Pyright、前后端与新增 Host 依赖边界、源码长度均通过 |
| `pnpm test` + 新增 Host 回归 | 前端 108 项、Runtime 101 项、Host 8 项；含结构化消息/ID、JSON/XML/Unicode/截断、权限凭据、路径和 symlink、已有 staged/unstaged/untracked 变更保留、大文件按需读取、审批拒绝/失效、取消与队列、人工编辑冲突、验证过期及 Host 崩溃后的进程组清理 |
| Rust | `pnpm check:rust` 与 `pnpm test:rust` 通过，3 项 Rust 单元测试通过 |
| Web / Sidecar / 应用 | Web、release Sidecar、`.app` 和 `.dmg` 均构建成功；DMG 使用 CI 模式跳过 Finder 外观脚本，正式签名/公证未进行 |
| 分发资源 | Host/Node/SDK 为实际文件布局，避免 Tauri 漏复制 pnpm 链接；包内 19 个 Host 模块与当前构建摘要一致，不依赖全局 Node 或 Pi |
| 最终应用包的脚本化闭环 | 直接调用 `.app` 内 Runtime、Node 和 Pi，完成 read → write → 检查失败（退出码 1）→ 修复 → 通过（退出码 0）；证据 `.build/coding-packaged-fake.json` |
| 最终应用包普通聊天回归 | 发布 Sidecar 的 Fake 文本生成、取消、Worker 重启、Runtime 重启后的历史、资源指标及退出均通过 |
| 最终应用包 API 回归 | 2 项端到端场景通过：幂等提交、审批、失败修复、版本撤销与普通聊天回归；拒绝/取消、排队及审批时不持推理锁 |
| 最终应用包的真实 MLX 闭环 | 同机 Qwen3.8-27B-Uncensored-MLX 4-bit / mlx-vlm 0.6.14，真实 read / write / run_command 共 3 次工具调用，模型发起检查及宿主收尾检查退出码均为 0；证据 `.build/coding-packaged-real.json` |
| 浏览器 | 验证了发送与两次独立审批、失败后的修复、验证退出码与旧记录过期显示；Runtime 重启后的会话恢复、按需读取修改内容；界面证据 `.build/coding-ui-final.png` |

安装制品位于忽略目录 `apps/desktop/src-tauri/target/release/bundle/`，没有提交模型、私有诊断或构建产物。本次新增依赖仅用于 Pi Host，不新增 Python 推理系统或 SQLite 原生模块。

上述真实模型验证只覆盖固定隔离项目的工具闭环，不能推定任意真实项目都能自动修复，也不能扩展为所有模板、长上下文、多模态 Coding 或长期稳定性结论。推理响应目前在完整结构化解析后发送，正文逐 Token 展示仍未实现。Worktree、PTY、外部 Skills/MCP、多 Agent 和周期任务按原设计属于后续阶段；正式签名、公证、干净机器及长期压力验收仍未进行。

### 首轮多工具调用回归（2026-10-16）

用户的“完成一个简单的web图书馆系统”任务暴露了固定单调用探针遗漏的问题：原解析器将同一响应中的多个 `<tool_call>` 当作格式错误，Host 又将具体错误归并为 `MODEL_INFERENCE_FAILED`。`mlx-tools-v2` 先校验完整调用批次，再通过已声明顺序执行的 Pi 工具逐个执行；每次命令仍独立审批。截断、缺失结束标记、未知工具及超过 48 个调用的批次整体拒绝。模型错误保留稳定 Runtime 错误码，界面显示中文说明与详情；不存储任意 Provider 错误正文。工具验证探针现在明确要求首轮同时发起目录列表和文件读取。

源码运行的同机真实 Qwen 模型已在隔离空目录完成原文任务：首轮 list / git_status、第二轮两个独立 write 均正常顺序执行，最终生成 HTML、CSS、JS 和使用说明，7 次工具调用，审批后的 `node --check app.js && ls -la` 退出码 0，任务终态 completed / passed。非 Git 空目录的 git_status 返回工具错误，模型正常继续；没有改动用户原项目。证据 `.build/coding-multicall-real-task.json` 及相邻 `.project/`。

Chrome 手工回归通过初始书目、添加、实时搜索、借出后库存减少、刷新后借阅保存、归还后库存恢复、删除及关联记录清理；页面无 console error。内置浏览器不支持原生 prompt，借阅弹窗由 Chrome 原生界面完成。证据 `.build/coding-library-browser.json`、`.build/coding-library-regression.png`。

最终 `.app` 内真实 MLX 再验收通过：新的批量调用探针共 4 次工具调用，模型检查与宿主收尾检查退出码均为 0；脚本化探针共 7 次工具调用，退出码序列 `[1, 0, 0]`。证据 `.build/coding-multicall-packaged-real.json`、`.build/coding-multicall-packaged-fake.json`。包内 19 个 Host 模块与源码构建摘要一致。重新构建 Host 后验证工作区仍同时保留运行依赖与开发工具；构建失败路径也执行依赖恢复。最终本机临时签名包及 `/Applications/MLX Studio.app` 通过 `codesign --verify --deep --strict`；保持 hardened runtime，声明 Python/MLX 动态库加载所需权限。签名后的独立 Runtime 真实模型 4 次工具调用、两个退出码 0，Fake 失败修复 `[1, 0, 0]` 均通过，证据 `coding-multicall-signed-real.json` / `coding-multicall-signed-fake.json`。正式 Developer ID 签名与公证未进行。

最终安装版桌面启动、Runtime 就绪、当前两条开发会话及 Qwen 工具验证状态恢复均已实际确认。用户授权关闭运行中的源码开发版后，在 `/Applications/MLX Studio.app` 创建独立“安装版回归验收（只读）”会话：真实 Qwen 在单一模型响应中发起 list / git_status，按序完成，任务 completed；只读任务无命令检查，正确保留 not_run。原项目目录仍为空。证据 `.build/coding-installed-real.json`、`.build/coding-installed-regression.png`。界面已恢复开发模式，保留安装版窗口。连接中断与超时也已映射为独立稳定错误码和中文提示。

## 后续工作与发布条件

| 方向 | 剩余工作及验收要求 |
|---|---|
| 模型与下载 | 扩展真实架构/量化矩阵；完善下载进度、跨重启恢复及磁盘压力处理 |
| 多模态 | 扩展连续图片追问、多图/像素解码限制；实时语音与视频能力后续评估 |
| 图片创作 | 扩展编辑素材、蒙版边界质量、十参考图、高分辨率和其他模型/导出；批量、LoRA 等扩展单独确定范围 |
| 稳定性 | 真模型故障注入、自动退避恢复、长时间运行、连续切换/取消与 Worker RSS 回收对照 |
| 性能与安全 | 固定设备/模型/参数的 TTFT、吞吐、内存与生图基线；路径/超大附件/Markdown/日志隐私及诊断导出验收 |
| 外部 API | 当前默认关闭；兼容聊天接口返回 501，协议、流式响应和独立认证需完成后再开放 |
| 桌面交付 | PyInstaller/MLX 动态库打包、退出清理、嵌套签名、公证、更新/回滚、数据迁移、首次启动引导 |

正式发布仍需执行 `pnpm build:app`，并在无开发工具/Python 的干净 Apple Silicon Mac 上验证安装、Sidecar、离线使用、历史保留、退出清理和 Gatekeeper。至少覆盖两种内存规格，升级失败时旧版本可启动、会话/模型登记/作品完整，卸载不得默认删除外部模型目录。

质量检查通过、Web 构建成功或某个本地模型通过，均不能代替这些发布条件。后续验收结果直接更新本文件，不再累积旧 P0–P9 阶段状态或临时修复日报。


## Coding 界面简化（2026-10-16）

- 顶部移除运行验证、项目设置、验证，仅保留变更与文件。对话、输入与可调整宽度的完整右侧浏览面板并列。
- 文件使用 Naive UI 目录树和 CodeMirror 只读源码；变更使用 Diff2Html，支持行内/并排、本会话/Git、打开文件与冲突保护撤销。依赖许可随包保留。
- 发送时自动准备首次使用的模型，失败保留输入；普通任务不再执行旧项目验证命令，命令工具继续逐次审批。
- 源码检查、117 项前端测试、102 项 Runtime 测试、8 项 Host 测试与 Web 构建通过。浏览器隔离项目验收覆盖目录搜索、空文件、源码搜索、红绿与并排差异、Git 列表内部跳转及面板拖动。
- 新版 `.app` / `.dmg` 构建通过，`codesign --verify --deep --strict` 通过，已更新 `/Applications/MLX Studio.app`；旧版保存在 `.build/application-backups/MLX Studio-before-ui-redesign-20261016.app`。
- 最终安装版的独立 Runtime + 内置 Node Host 工具探针通过：7 次工具调用，预期先失败再修复的退出码为 `[1, 0, 0]`，证据 `.build/coding-ui-installed-fake.json`。首次直接发送任务的自动准备浏览器验收记录 `.build/coding-ui-auto-prepare.json`。
- 桌面已确认仅剩“变更、文件”，原项目的文件访问曾等待 macOS 重新授权文稿目录（临时签名更新导致旧授权不匹配）。用户已允许最终安装包访问，现已恢复；正式签名、公证及干净机器验收仍未完成。
- 安装版桌面隔离项目验收通过：自动准备/发送、逐次命令审批、失败后修复、受管差异、文件树搜索、TypeScript 动态语法模块与 ⌘F 源码搜索。会话名“界面回归验收（隔离）”，只修改隔离项目的 `probe.txt`；任务完成，检查退出码 `[1, 0]`，无额外收尾检查。证据 `.build/coding-ui-installed-task.json`，截图 `.build/coding-ui-installed.png`。

本次主要改动文件：

- `apps/desktop/src/modules/coding/pages/CodingPage.vue` / `CodingPage.styles.css`：简化入口与左右面板布局。
- `components/CodingInspector.vue`、`CodingChangesView.vue`、`CodingFileBrowser.vue`、`CodePreview.vue`、`DiffPreview.vue`：开源查看器与目录浏览（以上组件路径均位于 `apps/desktop/src/modules/coding/`）。
- `presentation/coding-controller.ts`、`coding-inspector-controller.ts`、`coding-activity.ts` 与 `infrastructure/code-preview.ts`、`diff-preview.ts`、`domain/inspector.ts`：自动模型准备、独立浏览状态与安全渲染（同一 Coding 模块）。
- `apps/desktop/src/capabilities/coding-settings/presentation/CodingSettingsPanel.vue`、`components/CodingComposer.vue` / `CodingTimeline.vue`（Coding 模块）：清理旧验证/修复轮数界面与折叠操作记录。
- `services/coding-agent/src/application/runs.ts` / `adapters/workspace.ts`：普通任务不运行旧配置检查，新仓库 Git 差异正确展示工作树。
- `apps/desktop/package.json`、`pnpm-lock.yaml`、`apps/desktop/public/third-party-notices.txt`：添加查看器依赖，保留 57 项依赖许可；新增相应单元/集成回归用例，更新 `docs/coding.md` 与本文。

检查记录：`pnpm check`；`pnpm test`（117 前端 + 102 Runtime + 8 Host）；最后控制器调整后重新运行 `pnpm check` / `pnpm test:frontend`，Git 调整后重新运行 `pnpm check:coding` / `pnpm test:coding`；`pnpm build:web`、`pnpm build:coding:bundle`、`CI=true pnpm --filter @mlx-studio/desktop tauri build --ci` 均通过。Web 构建保留大于 500 kB 的主包提示，查看器已按需拆分；本次未改 Rust 或 Python 生产代码，未重复 Rust 检查或真实 MLX 长任务，之前真实模型回归记录仍保留。

### 原项目授权后的最终验收补充

用户已在 macOS 文稿目录提示中允许访问。安装版重新切回原项目后，原有会话、四个项目文件（`app.js`、`index.html`、`README.md`、`style.css`）与 HTML 源码正常加载；四个受管文件差异正常读取，未修改原项目文件。

此次补查修正了 Diff2Html 将 `/dev/null` 到新文件误判为重命名的展示问题：受管新增文件现在带明确的 Git 新文件标记，并以 A 显示；现有空文件仍标为修改。新增路径含空格/中文和空文件区分的回归覆盖。`pnpm check`、`pnpm test` 再次全部通过：119 项前端 + 102 项 Runtime + 8 项 Host，共 229 项。

最终包已重新生成、安装并通过签名完整性检查；用户允许最终包访问文稿目录后，再次在安装版中打开原项目，四个文件均正确显示 A，`app.js` 差异标记为 ADDED，点击“打开文件”成功读取原始 JavaScript 源码并显示语法着色。无目录权限错误或待处理的系统授权。本次补查仅修改 `diff-preview.ts`、`diff-preview.spec.ts`、`CodingChangesView.vue` 与本文，未新增依赖，未修改用户项目文件。

最终截图：`.build/coding-ui-original-project-changes.png`、`.build/coding-ui-original-project-files.png`。完整源码检查、229 项测试、Web/桌面构建、安装版隔离任务及原项目文件/变更读取验收完成。

## 语音创作（2026-10-17）

已实现独立工作区、模式筛选、模型识别与资源完整性契约、参考 WAV 校验、音色保存/编辑/授权/完整删除、作品历史/复用/试听/波形/WAV 导出。语音与聊天、图片、Coding 共用调度和单活 Worker，增加音频 SQLite 迁移与媒体恢复，默认删除音色后保留的录音可单独管理。新增固定可选依赖 mlx-audio 0.5.9，没有新增前端依赖。

源码 Runtime 已在本机验证固定 revision 的 Qwen3-TTS 1.7B CustomVoice 8bit 预设合成和 0.6B Base 8bit 参考克隆（24 kHz WAV），离线 Worker、运行取消/取消后再生成、卸载退出、重启后作品恢复通过。参考素材来自模型生成的测试样本，没有使用私人录音。自动化及参数、时长、RTF、固定模型 revision 与本地证据见[语音创作](./audio-studio.md)。

声音设计、ASR、录音、长文分段、原生音频流、Kokoro/VoxCPM2 尚未开放。新增语音能力的发布 Sidecar、原生 WebView 导出、签名/公证、干净机器、长文质量及音色相似度专项验收尚未执行；不把源码真机验证当作安装包验收。

`pnpm check`、`pnpm test`（127 项前端 + 116 项 Runtime + 8 项 Coding，共 251 项）、`pnpm build:web` 通过。浏览器隔离数据的音色导入/保存、真实预设合成/克隆、切页恢复、试听、参数复用、WAV 下载及窄窗口布局通过，控制台无错误。源码最终 Worker 额外短文本克隆冒烟成功。没有自动 commit 或 push。

## 移除默认模拟模型（2026-10-17）

正常 Runtime 启动不再自动登记 Fake Text/Image/Speech 模型。SQLite 迁移 6 只移除 `source=builtin`、`engine=fake` 的旧登记，保留真实模型、原模型文件和历史快照；新数据库默认为空模型列表。测试与隔离验收脚本改为显式登记模拟模型，不增加面向用户的开关或新依赖。

当前开发版模型库的 3 个 Fake 条目已清理，5 个真实模型（含两款 Qwen3-TTS）完整保留，在线模型列表已验证。`pnpm check` 和 `pnpm test` 通过（127 前端 + 118 Runtime + 8 Coding，共 253 项）；新增空库启动/重启、旧库迁移保留真实权重与历史的回归测试。

本次修改 `application/model_catalog.py`、`adapters/persistence/model_migrations.py` / `sqlite_repositories.py`，并将模拟登记移到 `tests/runtime_fixtures.py` 与 `scripts/verification_models.py`。相关测试、隔离验证脚本及使用说明同步更新；没有新增依赖，没有重新构建或替换安装包，没有提交或推送代码。
