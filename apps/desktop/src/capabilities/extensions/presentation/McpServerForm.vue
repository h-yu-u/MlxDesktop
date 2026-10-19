<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCheckbox,
  NCollapse,
  NCollapseItem,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NSwitch,
} from 'naive-ui'
import type { ExtensionServer, ExtensionInventory, McpWriteRequest } from '@mlx-studio/api-client'
import { SubmissionIdentity } from '../../requests'
import { parsePublicMcpDraft } from './mcp-config'
const props = defineProps<{
  server: ExtensionServer | null
  inventory?: ExtensionInventory
  pending: boolean
  saveRequest: (value: McpWriteRequest) => Promise<boolean>
}>()
const identity = new SubmissionIdentity()
const name = ref(''),
  type = ref<'stdio' | 'streamable-http'>('stdio'),
  executable = ref(''),
  args = ref('[]'),
  cwd = ref(''),
  url = ref(''),
  publicValues = ref('{}'),
  enabled = ref(false)
const credentialAction = ref<'keep' | 'replace' | 'clear'>('keep'),
  credentialKind = ref<'bearer' | 'api-key' | 'env'>('env'),
  credentialField = ref('API_KEY'),
  secret = ref(''),
  error = ref('')
const allowed = ref<string[]>([]),
  readOnly = ref<string[]>([])
const discovered = computed(() => props.inventory?.tools ?? [])
const importedJson = ref('')
function importJson(): void {
  try {
    const draft = parsePublicMcpDraft(importedJson.value)
    name.value = draft.name
    enabled.value = draft.enabled ?? false
    allowed.value = draft.allowedTools ?? []
    readOnly.value = draft.readOnlyTools ?? []
    type.value = draft.transport.type
    if (draft.transport.type === 'stdio') {
      executable.value = draft.transport.executable
      args.value = JSON.stringify(draft.transport.args)
      cwd.value = draft.transport.cwd
      publicValues.value = JSON.stringify(draft.transport.publicEnv, null, 2)
    } else {
      url.value = draft.transport.url
      publicValues.value = JSON.stringify(draft.transport.publicHeaders, null, 2)
    }
    error.value = ''
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '配置格式不正确'
  }
}
watch(
  type,
  (value) => {
    credentialKind.value = value === 'stdio' ? 'env' : 'bearer'
    credentialField.value = value === 'stdio' ? 'API_KEY' : 'Authorization'
  },
  { flush: 'sync' },
)
watch(
  () => props.server,
  (server) => {
    name.value = server?.name ?? ''
    enabled.value = server?.enabled ?? false
    allowed.value = [...(server?.allowedTools ?? [])]
    readOnly.value = [...(server?.readOnlyTools ?? [])]
    const transport = server?.transport
    type.value = transport?.type ?? 'stdio'
    executable.value = transport?.type === 'stdio' ? transport.executable : ''
    cwd.value = transport?.type === 'stdio' ? transport.cwd : ''
    args.value = JSON.stringify(transport?.type === 'stdio' ? transport.args : [])
    url.value = transport?.type === 'streamable-http' ? transport.url : ''
    publicValues.value = JSON.stringify(
      transport?.type === 'stdio' ? transport.publicEnv : (transport?.publicHeaders ?? {}),
      null,
      2,
    )
    credentialAction.value = 'keep'
    credentialKind.value =
      transport?.type === 'streamable-http'
        ? transport.authMode === 'api-key'
          ? 'api-key'
          : 'bearer'
        : 'env'
    credentialField.value =
      Object.keys(transport?.secretRefs ?? {})[0] ??
      (type.value === 'stdio' ? 'API_KEY' : 'Authorization')
    identity.clear()
    secret.value = ''
    error.value = ''
  },
  { immediate: true },
)
function toggle(values: string[], name: string, checked: boolean): string[] {
  return checked ? [...new Set([...values, name])] : values.filter((item) => item !== name)
}
function publicMap(text: string): Record<string, string> {
  const value: unknown = JSON.parse(text)
  if (
    !value ||
    typeof value !== 'object' ||
    Array.isArray(value) ||
    Object.values(value).some((item) => typeof item !== 'string')
  )
    throw new Error('公开配置必须是字符串键值对象')
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, String(item)]))
}
async function save(): Promise<void> {
  if (props.pending) return
  error.value = ''
  try {
    const values = publicMap(publicValues.value),
      argv: unknown = JSON.parse(args.value)
    if (!Array.isArray(argv) || argv.some((item) => typeof item !== 'string'))
      throw new Error('参数必须是 JSON 字符串数组')
    const transport =
      type.value === 'stdio'
        ? {
            type: type.value,
            executable: executable.value,
            args: argv.map(String),
            cwd: cwd.value,
            publicEnv: values,
          }
        : {
            type: type.value,
            url: url.value,
            publicHeaders: values,
            authMode:
              credentialAction.value === 'replace'
                ? credentialKind.value === 'bearer'
                  ? ('bearer' as const)
                  : ('api-key' as const)
                : props.server?.transport.type === 'streamable-http'
                  ? props.server.transport.authMode
                  : ('none' as const),
          }
    const credential =
      credentialAction.value === 'replace'
        ? {
            action: 'replace' as const,
            field: credentialField.value,
            kind: credentialKind.value,
            value: secret.value,
          }
        : credentialAction.value === 'clear'
          ? { action: 'clear' as const, field: credentialField.value }
          : { action: 'keep' as const }
    const intent = {
      ...(props.server ? { id: props.server.id } : {}),
      expectedRevision: props.server?.revision ?? 0,
      name: name.value,
      enabled: enabled.value,
      transport,
      credential,
      allowedTools: allowed.value,
      readOnlyTools: readOnly.value.filter((item) => allowed.value.includes(item)),
    }
    if (await props.saveRequest({ ...intent, mutationId: identity.for(intent) })) {
      secret.value = ''
      identity.clear()
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '配置格式不正确'
  }
}
</script>
<template>
  <NForm label-placement="top" @submit.prevent="save">
    <NAlert v-if="error" type="error">{{ error }}</NAlert>
    <NCollapse
      ><NCollapseItem title="导入公开配置 JSON" name="json">
        <p>使用本产品的 name、transport、allowedTools 等字段。导入后先审阅表单，凭据单独填写。</p>
        <NInput v-model:value="importedJson" type="textarea" aria-label="公开 MCP 配置 JSON" />
        <NButton :disabled="!importedJson.trim()" @click="importJson">填入表单</NButton>
      </NCollapseItem></NCollapse
    >
    <NFormItem label="服务名称"><NInput v-model:value="name" :maxlength="80" /></NFormItem>
    <NFormItem label="连接方式"
      ><NSelect
        v-model:value="type"
        :options="[
          { label: '本地进程（stdio）', value: 'stdio' },
          { label: '远程 HTTP', value: 'streamable-http' },
        ]"
    /></NFormItem>
    <template v-if="type === 'stdio'">
      <NFormItem label="可执行文件绝对路径"
        ><NInput v-model:value="executable" placeholder="已安装的服务入口或 Node 路径"
      /></NFormItem>
      <NFormItem label="参数数组（JSON）"
        ><NInput v-model:value="args" type="textarea"
      /></NFormItem>
      <NFormItem label="工作目录绝对路径"><NInput v-model:value="cwd" /></NFormItem>
    </template>
    <NFormItem v-else label="服务 URL"
      ><NInput v-model:value="url" placeholder="https://example.com/mcp"
    /></NFormItem>
    <NFormItem :label="type === 'stdio' ? '公开环境变量（JSON）' : '公开 headers（JSON）'"
      ><NInput v-model:value="publicValues" type="textarea"
    /></NFormItem>
    <NFormItem :label="server?.credentialConfigured ? '凭据（已配置）' : '凭据'"
      ><NSelect
        v-model:value="credentialAction"
        :options="[
          { label: '保持现有', value: 'keep' },
          { label: '替换', value: 'replace' },
          { label: '清除指定字段', value: 'clear' },
        ]"
    /></NFormItem>
    <template v-if="credentialAction !== 'keep'">
      <NFormItem label="秘密字段名称"
        ><NInput
          v-model:value="credentialField"
          :placeholder="type === 'stdio' ? 'API_KEY' : 'Authorization'"
      /></NFormItem>
      <template v-if="credentialAction === 'replace'">
        <NFormItem label="认证方式"
          ><NSelect
            v-model:value="credentialKind"
            :options="
              type === 'stdio'
                ? [{ label: '环境变量', value: 'env' }]
                : [
                    { label: 'Bearer', value: 'bearer' },
                    { label: 'API Key', value: 'api-key' },
                  ]
            "
        /></NFormItem>
        <NFormItem label="一次性凭据值"
          ><NInput
            v-model:value="secret"
            type="password"
            show-password-on="click"
            :input-props="{ autocomplete: 'off' }"
        /></NFormItem>
      </template>
    </template>
    <NFormItem label="启用（下次任务生效）"><NSwitch v-model:value="enabled" /></NFormItem>
    <NAlert type="info"
      >保存后测试连接以发现工具，再明确授权工具。只读分类是你的本地授权，请核实服务权限范围；服务自报的提示不授予权限。</NAlert
    >
    <NSpace v-for="tool in discovered" :key="tool.id" align="center" style="margin-top: 8px">
      <NCheckbox
        :checked="allowed.includes(tool.originalName)"
        @update:checked="allowed = toggle(allowed, tool.originalName, $event)"
        >{{ tool.originalName }}</NCheckbox
      >
      <NCheckbox
        :disabled="!allowed.includes(tool.originalName)"
        :checked="readOnly.includes(tool.originalName)"
        @update:checked="readOnly = toggle(readOnly, tool.originalName, $event)"
        >已确认只读</NCheckbox
      >
    </NSpace>
    <NButton
      type="primary"
      attr-type="submit"
      :loading="pending"
      :disabled="!name.trim()"
      style="margin-top: 16px"
      >保存配置</NButton
    >
  </NForm>
</template>
