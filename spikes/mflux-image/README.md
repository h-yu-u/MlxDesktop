# P0-04：MFLUX 文生图 Spike

```bash
uv run --project spikes/mflux-image --python 3.12 python spikes/mflux-image/run_image_generation.py
```

可设置模型、prompt、seed、steps、width、height 和输出路径。默认 PNG 在临时目录中生成、校验后自动清除；指定 `--output` 才会保留图片。成功标准是 PNG 签名和宽高均与请求一致。

本机尚未下载 MFLUX 依赖或模型，因此候选模型和 Python API 调用仍未完成真实硬件验证。
