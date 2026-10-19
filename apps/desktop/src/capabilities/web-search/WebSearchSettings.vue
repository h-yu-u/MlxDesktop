<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NAlert, NButton, NCard, NForm, NFormItem, NInput, NSpace, useMessage } from 'naive-ui'
import { useWebSearch } from './store'
const web = useWebSearch(),
  message = useMessage()
const baseUrl = ref('https://api.tavily.com'),
  apiKey = ref('')
onMounted(async () => {
  await web.load()
  if (web.settings) baseUrl.value = web.settings.baseUrl
})
async function save(): Promise<void> {
  if (
    await web.save({
      expected_revision: web.settings?.revision ?? 0,
      provider: 'tavily',
      base_url: baseUrl.value,
      api_key: apiKey.value || undefined,
    })
  ) {
    apiKey.value = ''
    message.success('联网设置已保存，请测试连接')
  }
}
async function test(): Promise<void> {
  if (await web.test()) message.success('搜索服务连接成功')
}
</script>
<template>
  <NCard title="联网搜索" style="margin-top: 16px">
    <p>使用 Tavily Search / Extract 获取参考资料，回答由当前本地模型生成。</p>
    <NForm label-placement="top">
      <NFormItem label="Tavily 服务地址"
        ><NInput v-model:value="baseUrl" :disabled="web.pending" aria-label="搜索服务地址"
      /></NFormItem>
      <NFormItem
        :label="web.settings?.credentialConfigured ? 'API Key（已保存，留空沿用）' : 'API Key'"
      >
        <NInput
          v-model:value="apiKey"
          type="password"
          placeholder="输入 API Key"
          autocomplete="off"
          :disabled="web.pending"
          aria-label="搜索 API Key"
        />
      </NFormItem>
    </NForm>
    <NAlert v-if="web.error" type="error">{{ web.error }}</NAlert>
    <NSpace
      ><NButton :loading="web.pending" @click="save">保存</NButton
      ><NButton :disabled="web.pending || !web.settings?.credentialConfigured" @click="test"
        >测试连接</NButton
      ></NSpace
    >
    <p>搜索关键词会发送给所配置的搜索服务，附件在本地解析。密钥保存在系统安全存储中。</p>
    <p v-if="web.settings?.ready">连接已验证 · 配置版本 {{ web.settings.revision }}</p>
  </NCard>
</template>
