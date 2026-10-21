<script setup lang="ts">
import PageHeader from '../../../shared/ui/PageHeader.vue'
</script>
<template>
  <section>
    <PageHeader title="隐私与数据" subtitle="了解本机存储与外部服务的数据流向" />
    <p>
      模型推理在本机进行。会话和生成文件保存在本机；日志默认不记录完整提示词、模型输出或附件内容。
    </p>
    <p>
      启用联网搜索后，查询关键词会发送给配置的服务。启用 MCP
      工具后，调用参数和结果会与对应服务交换。请按需要选择能力及逐次授权。
    </p>
    <p>内部 Runtime 仅监听回环地址，桌面会话令牌不落盘。兼容 API 默认关闭。</p>
  </section>
</template>
