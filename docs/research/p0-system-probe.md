# P0-01：系统探针

探针只读取当前开发机的硬件、系统、Python 和磁盘信息，不安装依赖、不访问网络，也不读取模型目录。Metal 信息来自 macOS `system_profiler`；缺少对应字段时会明确记为未知，不会把未知误报为不支持。

## 运行

```bash
python3 scripts/system_probe.py
python3 scripts/system_probe.py --output benchmarks/p0-baseline.json
```

`--root` 可指定要检查容量的目录；默认检查当前目录所在文件系统。结果是 JSON，字节数保留原始整数以便后续比较。芯片、系统命令或 Metal 字段不可读取时对应值为 `null`，Python 和磁盘信息则由当前运行环境采集。

## 当前基线

`benchmarks/p0-baseline.json` 是本开发机的一次采集快照。它描述采集时环境，不代表最低配置或兼容性承诺；P0 完成后应根据固定测试模型与干净机器验证补充正式结论。
