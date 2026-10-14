# 使用与开发

[文档入口](./README.md)

## 环境与启动

桌面应用面向 Apple Silicon macOS。开发环境使用 Node.js 22、pnpm 11、uv 管理的 Python 3.12、Rust stable（至少 1.77.2）和 macOS Command Line Tools。仓库提供 `.nvmrc`；依赖版本由锁文件约束。

在仓库根目录执行：

```bash
nvm use
pnpm bootstrap
pnpm dev
```

`bootstrap` 安装前端依赖与 Runtime 的 `mlx-vlm`、`mflux` 可选依赖。桌面 Debug 启动使用项目 Runtime；发布版本使用打包后的 Sidecar。首次安装依赖及下载模型需要网络。

`pnpm dev:web` 只启动前端开发服务器。完整本地交互还需要 Runtime 连接；FakeEngine 可用于无真实模型的 API/UI 开发。

## 模型库

1. 打开“模型库”，展开 Hugging Face 模型下拉列表。
2. 输入名称或关键词搜索，选择仓库后点击“下载模型”。
3. 下载完成后自动登记到本地模型库；返回聊天或图片创作页选择使用。

目录通过 Hugging Face 公开 API 按 `mlx` 元数据筛选、按下载量排序，只显示无需申请访问的仓库。目录查询不读取或发送本机 HF 凭据；模型下载使用 Runtime 的 `huggingface-hub` 适配器。出现在目录中或下载成功不代表已验证兼容，具体范围见[验收状态](./status.md)。

默认下载位置为 `~/MLXModels`，可由 Runtime 的模型目录设置覆盖。下载期间可切换页面，需要保持应用运行；失败可重试，已登记的同一 HF 仓库不会重复发起下载。跨应用重启的下载恢复尚需完善。

已有模型可直接导入本地目录。目录必须包含完整的模型配置和权重；扫描仅检查静态元数据与文件结构，不执行仓库代码。移除模型登记与删除磁盘文件是独立操作。

## 聊天

聊天页优先选择已登记的真实文本模型，首次发送时自动加载。后续轮次使用已保存的对话历史；生成中可停止，连接失效后可重新启动 Runtime。发送失败会保留草稿和附件。

已验证的 Qwen3.8-27B MLX 模型应导入包含 `config.json` 和权重的 `4-bit` 子目录。当前已验证纯文本场景；模型经 `mlx-vlm` 运行不代表图片理解已经验收。没有真实模型时可选择明确标注的 Fake Text Engine 验证交互。

## 图片创作与历史

1. 选择本地生图模型，填写提示词、比例或尺寸、步数和 Seed；Seed 留空时随机生成。
2. 提交任务，查看排队、准备和生成进度；运行中可取消。
3. 完成后自动保存 PNG 和参数。在页面顶部点击“作品历史”，进入下方历史画廊。
4. 点击缩略图预览大图、导出 PNG，或复用模型、提示词、尺寸、步数和 Seed。

图片任务与聊天共用单个推理 Worker，忙碌时排队；切换页面不会丢失任务。失败或重启中断的任务保留参数，可从“最近任务”复用后再生成；中断任务不会自动续算。历史记录在应用重启后仍可查看。

Runtime 接口允许宽高 64–2048 且为 16 的倍数，步数 1–100，Seed 为 0–4294967295；这只是参数校验范围，不能据此推定所有模型和分辨率已验证。

Qwen Image 2.1 原生 MFLUX 导出应包含 `transformer/`、`text_encoder/`、`vae/` 的分片索引和权重，以及 `processor/` 分词器。模型通过结构识别，目录名称不影响行为。生成时只使用本地权重，不隐式下载缺失组件。Fake Image Engine 会明确标注为模拟图像。

## 数据位置

| 数据 | 位置 |
|---|---|
| 桌面应用数据 | Tauri `app_data_dir()`，应用标识为 `local.mlxstudio.app` |
| 数据库 | 应用数据目录内 `app.db`；保存会话、模型、任务和作品元数据 |
| 生成图片 | 应用数据目录对应的 `media/images/` |
| 下载模型 | 默认 `~/MLXModels`，与应用数据分开保存 |

桌面壳通过 `MLX_STUDIO_DATA_DIR` 将数据目录交给 Runtime。独立运行 Runtime 且未指定目录时，数据库默认在 `~/Library/Application Support/MLX Studio/data/app.db`，媒体文件在同一应用目录的 `media/`。备份历史时应同时保留数据库和媒体文件。

## 常用检查与构建

以下命令均在仓库根目录执行，具体脚本以 [package.json](../package.json) 为准。

| 命令 | 用途 |
|---|---|
| `pnpm check` | 前端类型与 lint、Runtime Ruff/Pyright、依赖边界检查 |
| `pnpm test` | 前端 Vitest 和 Runtime unittest |
| `pnpm api:generate` | 根据 FastAPI OpenAPI 更新 API 类型 |
| `pnpm check:rust` | Rust fmt 与 clippy |
| `pnpm build:web` | 构建 Vue 前端 |
| `pnpm build:runtime:check` | Python 源码编译检查；`build:runtime` 为其别名 |
| `pnpm build:sidecar` | Apple Silicon macOS 上构建 PyInstaller Runtime |
| `pnpm build:app` | Web → Sidecar → Tauri `.app`/`.dmg`；`build:desktop` 为其别名 |

Web 构建和源码检查不能代替打包应用、签名、公证或干净机器验收。真实模型复验命令见[验收状态](./status.md)。
