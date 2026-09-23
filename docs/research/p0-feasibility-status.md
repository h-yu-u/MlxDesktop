# P0 可行性状态

| 任务 | 本地实现/验证 | 当前结论 |
|---|---|---|
| P0-01 系统探针 | 探针和 Apple Silicon 基线快照已生成 | 通过；本机系统 Python 3.9.6，不满足产品 Python 3.12 基线 |
| P0-02 mlx-lm 文本 | Spike 已实现；依赖 wheel 未完整下载 | 未验证真实模型；FakeEngine 的子进程流式链路已通过自动化用例 |
| P0-03 mlx-vlm 图片理解 | 独立 Spike 已实现 | 未验证真实模型 |
| P0-04 MFLUX 生图 | 独立 Spike 已实现并检查 PNG 签名/尺寸 | 未验证真实模型 |
| P0-05 IPC、取消、错误 | NDJSON Worker/Host、取消、协议版本、序号检查 | FakeEngine 路径已自动化验证；真实推理取消待测 |
| P0-06 内存回收 | Worker 终止和十轮重启测试 | 子进程退出行为通过；真实 MLX RSS 对比未测 |
| P0-07 Sidecar 打包 | PyInstaller 构建脚本和 Tauri externalBin 配置 | 未构建；当前主机未安装 Rust/Cargo，MLX 包装载也未验证 |
| P0-08 干净 Mac 安装 | 无干净测试机环境 | 未验证 |
| P0-09 固定模型兼容矩阵 | 维护了候选模型和 revision 字段 | 尚非已验证基线，候选项均标记 `verified: false` |

要把 P0 判定为完成，仍需在可下载 PyPI 与 Hugging Face 资源的 Apple Silicon 构建机上运行三类模型测试、Worker 内存对照和 Sidecar 干净安装。当前表格不会把 FakeEngine 结果折算成真实模型通过。
