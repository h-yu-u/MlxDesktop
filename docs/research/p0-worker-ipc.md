# P0-05 / P0-06：Worker IPC 和进程生命周期

Supervisor 与 Worker 使用 JSON Lines。每条命令都包含协议版本、命令 ID 和 payload；Worker 每个事件都包含协议版本、递增序号、事件类型和 payload。stdout 只供协议使用，诊断写入 stderr。非法 JSON 或协议版本不符会让 Worker 终止。

FakeEngine 子进程用例覆盖 readiness、load、逐段 delta、取消终态、正常完成、shutdown 和重启。十轮加载/生成/终止测试验证无残留运行中的 Worker 句柄。真实 MLX 的进程 RSS 回收和连续推理仍需 P0 模型环境验证。
