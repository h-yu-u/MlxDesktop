# 语音创作

[文档入口](./README.md) · [架构](./architecture.md) · [验收状态](./status.md)

语音创作是独立工作区，首版提供预设音色合成、参考音频克隆、音色保存/编辑/删除、作品历史、试听、参数复用和 WAV 导出。声音设计、自动转写、录音、实时音频流和长文分段编辑尚未开放。

## 使用

1. 在统一模型库下载或导入完整 Qwen3-TTS 模型。CustomVoice 用于预设音色；Base 用于克隆。模式切换会筛选兼容模型。未知架构及缺少 tokenizer、codec 或分片权重的模型不能用于语音生成。
2. 预设模式选择模型、语言、speaker，填写最多 2000 字的朗读内容后生成。
3. 克隆模式先在音色库导入 16 位 PCM WAV（8–96 kHz，单/双声道，0.1–30 秒，最多 12 MiB），填写准确参考原文、名称、语言、素材来源并确认声音使用权，再保存音色。建议使用 5–20 秒单人、低噪声录音。
4. 选择保存的音色，输入新的文字并生成。作品支持播放、波形、时长、采样率、复用参数、WAV 导出及删除。没有模型进度总量时只显示任务阶段。

Fake Speech Engine 只供隔离自动化测试使用，正常应用不登记或显示 Fake 模型，升级时清理旧的内置模拟模型条目。测试音不能朗读或克隆真实声音。真实模型的静态能力仍显示 `candidate`，不会因下载、扫描或单次成功自动变为已验证模型。

停止播放与取消生成分别由播放器和任务按钮处理。离开工作区只释放观察与播放资源，后台生成继续，返回后重新读取任务快照。重启导致的未完成任务标记为失败，作品历史保留。

## 数据与接口

- 使用原有 JobScheduler、ModelRuntime 和单活 Worker。聊天、Coding、图片、语音共享推理租约，Worker 采用组合分发，音频模型不会进入文本 EngineSession。
- 模型的 `speech` 描述模式、语言、speaker、长度限制、资源问题、验证状态和适配版本。样式、生成语速及流式播放均未开放；未知参数明确拒绝。
- 增量迁移 5 新增 `audio_assets`、`voice_profiles`、`audio_artifacts` 和语音幂等索引，保留旧模型安装 ID、会话及图片历史。音频文件置于应用 `media/audio/{references,generated,staging}`；数据库只存元数据。
- 提交时冻结音色版本、参考原文、授权记录、模型 revision/identity 与适配版本；音色后续修改不影响排队任务。同一请求编号重复提交返回原任务，不同输入使用同一编号返回冲突。
- 默认删除音色仅删除 profile。完整删除同时移除录音，受其他音色及所有未完成任务引用保护。未关联音色的参考录音可在音色库单独试听和删除；删除音色/参考录音不连带删除历史成品。
- 音频上传校验 RIFF/WAVE、16 位 PCM、真实帧数、大小、采样率、声道、时长、截断和全静音。生成文件在 Supervisor 再次校验后事务登记；失败/取消清理临时文件，重启隔离未登记文件。
- `/internal/v1/audio-assets` 提供导入、参考列表、内容读取及删除；`/voices` 提供音色 CRUD；`/audio-generations` 提供 202 提交、列表、快照及取消；`/audio-artifacts` 提供分页作品、内容读取和删除。均使用现有 Session Token。
- 前端经认证获取 Blob 后创建 Object URL，切页及连接失效时回收；Token 不出现在音频 URL。NDJSON 只传状态，WAV 写入受控目录，并保留统一 `generation.completed/cancelled/failed` 终态。

## 依赖与复验

新增可选依赖 `mlx-audio==0.5.9`，与现有 MLX 0.32.1 / mlx-vlm 0.6.14 / MFLUX 0.22.0 一起通过 uv 解算。没有新增前端依赖。Qwen 参数映射依据固定版本 [mlx-audio 源码](https://github.com/Blaizzy/mlx-audio/tree/v0.5.9/mlx_audio/tts/models/qwen3_tts)，不启动上游 Server。Worker 中延迟导入，强制离线加载完整本地资源；不在生成时安装依赖或下载 codec。

```bash
uv sync --project services/runtime --frozen --extra mlx-vlm --extra mflux --extra audio
pnpm api:generate
pnpm check
pnpm test
pnpm build:web
```

release Sidecar 构建脚本已纳入 audio extra 及相关动态依赖；fake profile 排除真实语音库。新增语音能力的 PyInstaller 产物、原生 WebView 音频导出、签名/公证与干净机器验收尚未执行。

## 本机验证（2026-10-17）

Apple Silicon / 64 GB，源码 Runtime、mlx-audio 0.5.9、MLX 0.32.1、关闭 JIT。两款模型准备完成后，语音 Worker 开启 HF/Transformers 离线模式，通过认证 API 验证：

| 模型 | 固定 revision | 结果 |
|---|---|---|
| `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit` | `41d3337e8b7f2843a75841595fc14e4b9a7a4b96` | 中文预设合成，24 kHz、2.72 秒 WAV |
| `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit` | `50f45ef0047cde7e84c2ef04326acb8ada2436a7` | 使用上项合成样本及对应原文克隆，24 kHz、3.44 秒 WAV |

此单次样本的 Worker 生成与写入耗时分别约 2.43 / 1.80 秒，RTF（耗时/音频时长）约 0.89 / 0.52；含准备与加载的总耗时约 17.84 / 4.13 秒。运行取消约 8.03 秒收敛，随后再次克隆成功；卸载后 Worker 退出，Runtime 重启后 3 项成品保留。这些测量不代表长文、其他语言、音色相似度、所有设备或稳定性能结论。

证据位于忽略的 `.build/audio-validation/real-v2/evidence.json`，样本为同目录 `preset.wav`、`clone.wav`，没有使用私人录音。自动化覆盖有效 WAV、分段完整写入、模式/资源检查、幂等冲突、授权/输入拒绝、排队及运行取消、迟到完成、事务失败清理、恢复隔离、切页恢复及 Object URL 回收；已有聊天、图片、Coding 回归保留。

浏览器隔离数据验收通过真实预设合成、参考 WAV 导入/来源确认/音色保存、Base 克隆、切页恢复、播放（readyState=4）、参数复用和 WAV 下载，控制台无错误；检查了桌面与窄窗口布局。截图位于 `.build/audio-validation/audio-studio.jpg`。质量检查 `pnpm check`、`pnpm test`（127 前端 + 116 Runtime + 8 Coding）和 `pnpm build:web` 通过；构建保留既有主包超过 500 kB 的提示。未执行本次语音安装包构建或验收，未提交或推送代码。

## 主要改动位置

- `apps/desktop/src/modules/audio-studio/`：创作、播放器、音色库、作品页，类型化用例、网关和 controller；组合根、导航和路由接入新工作区。
- `services/runtime/src/mlx_studio_runtime/domain/speech.py`、`domain/models.py`：模式能力、请求校验、稳定错误码及模型元数据兼容。
- Runtime 的 `application/speech_generation_service.py`、`voice_profile_service.py`、`audio_ports.py`：统一调度下的生成、不可变快照、音色及引用保护。
- Runtime 的 `adapters/audio_files.py`、`audio_engines/`、`speech_model_scan.py`、`persistence/audio_repository.py`：音频边界、Fake/Qwen 引擎、资源扫描、增量 SQLite 表和媒体恢复。
- Runtime 的 `entrypoints/http/audio_contracts.py`、`audio_routes.py`，Worker 入口及 Host：认证 API、受控文件命令与统一终态；Coding 推理入口同步拒绝非文本模型。
- `packages/api-client/src/audio-decoders.ts`、`audio-endpoints.ts`、`generated-schema.d.ts` 与 transport：后端生成 DTO、响应检查、认证上传及播放下载。
- `services/runtime/pyproject.toml`、`uv.lock`、`scripts/build-runtime.sh`、根 `package.json`：固定可选依赖、开发初始化与 Sidecar 依赖收集。
- `tests/test_audio_studio.py`、`test_audio_engines.py`、`test_runtime_worker.py` 与前端 controller/导航测试：契约、恢复、取消、故障及旧模块回归。
