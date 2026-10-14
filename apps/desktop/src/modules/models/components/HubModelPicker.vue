<script setup lang="ts">
import { useDebounceFn } from '@vueuse/core'
import { NAlert, NButton, NEmpty, NSelect, NTag, type SelectOption, useMessage } from 'naive-ui'
import { computed, h, onMounted } from 'vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import { useModelsStore } from '../stores/models.store'

const store = useModelsStore()
const message = useMessage()
const selected = computed(() => store.selectedHubModel)
const downloaded = computed(() => !!selected.value && store.items.some(
  (item) => item.source === 'huggingface' && item.displayName === selected.value?.repo_id,
))
const options = computed(() => {
  const items = [...store.catalog]
  if (selected.value && !items.some((item) => item.repo_id === selected.value?.repo_id)) items.unshift(selected.value)
  return items.map((item) => ({ label: item.repo_id, value: item.repo_id, downloads: item.downloads }))
})
const search = useDebounceFn((query: string) => { void store.searchCatalog(query) }, 350)
onMounted(() => { if (!store.catalog.length && !store.catalogLoading) void store.searchCatalog() })

function renderLabel(option: SelectOption): ReturnType<typeof h> {
  return h('div', { class: 'hub-option' }, [
    h('span', { class: 'hub-option-name' }, String(option.label)),
    h('small', `${Number(option.downloads ?? 0).toLocaleString()} 次下载`),
  ])
}

async function download(): Promise<void> {
  if (await store.pullModel()) message.success('下载完成，模型已加入本地模型库')
}
</script>

<template>
  <section
    class="panel hub-discovery"
    aria-label="从 Hugging Face 下载 MLX 模型"
  >
    <div class="hub-heading">
      <div class="hub-icon">
        <StudioIcon
          name="cube"
          :size="27"
        />
      </div>
      <div><h2>发现你的下一个模型</h2><p>从 Hugging Face 直接获取 MLX 模型，选择后即可下载到本机。</p></div>
      <NTag
        size="small"
        round
        :bordered="false"
      >
        Hugging Face · MLX
      </NTag>
    </div>
    <label
      class="hub-select-label"
      for="hub-model-picker"
    >选择模型 <span>热门排序 · 支持搜索仓库名称或关键词</span></label>
    <div class="hub-picker-row">
      <NSelect
        :input-props="{ id: 'hub-model-picker', 'aria-label': '搜索 MLX 模型' }"
        :value="store.selectedRepoId"
        :options="options"
        :loading="store.catalogLoading"
        :disabled="!!store.pullingRepoId"
        :render-label="renderLabel"
        filterable
        remote
        clearable
        size="large"
        placeholder="搜索 MLX 模型，例如 Qwen、Llama、Gemma…"
        aria-label="搜索并选择 Hugging Face MLX 模型"
        @search="search"
        @update:value="store.selectHubModel"
      >
        <template #empty>
          <NEmpty
            :description="store.catalogLoading ? '正在获取 Hugging Face 模型…' : store.catalogError ? '暂时无法获取模型，请重试' : '没有找到模型，换个关键词试试'"
            size="small"
          />
        </template>
      </NSelect>
      <NButton
        type="primary"
        size="large"
        :loading="!!store.pullingRepoId"
        :disabled="!selected || downloaded || !!store.pullingRepoId"
        @click="download"
      >
        <StudioIcon
          name="download"
          :size="19"
        />{{ store.pullingRepoId ? '正在下载' : downloaded ? '已在本地' : '下载模型' }}
      </NButton>
    </div>
    <div
      v-if="selected"
      class="hub-selection"
    >
      <StudioIcon
        name="cube"
        :size="21"
      />
      <div class="selected-model-info">
        <strong>{{ selected.repo_id }}</strong><span>{{ selected.task ?? 'MLX 模型' }} · {{ selected.downloads.toLocaleString() }} 次下载 · {{ selected.likes.toLocaleString() }} 个赞</span>
      </div>
      <NTag
        size="small"
        :bordered="false"
        :type="downloaded ? 'success' : 'info'"
      >
        {{ downloaded ? '已下载' : 'MLX' }}
      </NTag>
    </div>
    <NAlert
      v-if="store.catalogError"
      type="error"
      :show-icon="false"
      class="hub-notice"
    >
      {{ store.catalogError }}<NButton
        text
        type="primary"
        @click="store.searchCatalog(store.catalogQuery)"
      >
        重新获取
      </NButton>
    </NAlert>
    <NAlert
      v-if="store.pullingRepoId"
      type="info"
      :show-icon="false"
      class="hub-notice"
      aria-live="polite"
    >
      正在下载 {{ store.pullingRepoId }}，完成后自动加入本地模型库。你可以切换页面，保持应用运行即可。
    </NAlert>
    <NAlert
      v-else-if="store.downloadError"
      type="error"
      :show-icon="false"
      class="hub-notice"
      role="alert"
    >
      {{ store.downloadError }}<span> 可点击“下载模型”重试。</span>
    </NAlert>
    <NAlert
      v-else-if="store.lastDownloadedRepoId"
      type="success"
      :show-icon="false"
      class="hub-notice"
      aria-live="polite"
    >
      {{ store.lastDownloadedRepoId }} 已下载完成。
    </NAlert>
    <p class="hub-footnote">
      <StudioIcon
        name="info"
        :size="14"
      />仅列出公开、无需申请访问的 MLX 仓库；下载不代表模型已通过本机运行验证。
    </p>
  </section>
</template>

<style>
.hub-option { display: flex; align-items: center; justify-content: space-between; gap: 16px; width: 100%; min-width: 0; }
.hub-option-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hub-option small { color: #8999b5; font-size: 11px; flex-shrink: 0; }
</style>
<style scoped>
.hub-discovery { padding: 26px; margin: 20px 0 32px; background: radial-gradient(ellipse at 100% 0, #5147a326, transparent 65%), linear-gradient(120deg, #202b3e, #192332); }
.hub-heading { display: flex; align-items: center; gap: 16px; margin-bottom: 27px; }
.hub-icon { display: grid; place-items: center; width: 52px; height: 52px; flex-shrink: 0; border-radius: 15px; color: #a1afff; background: linear-gradient(135deg, #7263da45, #385f9c45); border: 1px solid #4b5381; }
.hub-heading h2 { margin: 0 0 6px; font-size: 19px; font-weight: 600; }.hub-heading p { margin: 0; color: #a8b7ce; font-size: 13px; line-height: 1.6; }.hub-heading > .n-tag { margin-left: auto; flex-shrink: 0; }
.hub-select-label { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; font-size: 13px; }.hub-select-label span { color: #8191ab; font-size: 11px; }
.hub-picker-row { display: flex; gap: 12px; }.hub-picker-row > .n-select { flex: 1; min-width: 0; }.hub-picker-row > .n-button { flex-shrink: 0; }.hub-picker-row .n-button :deep(.n-button__content) { gap: 8px; }
.hub-selection { display: flex; align-items: center; gap: 13px; padding: 17px 18px; margin-top: 16px; border-radius: 10px; border: 1px solid #35425b; background: #17213180; }.hub-selection > svg { color: #91a7fb; }.hub-selection > .n-tag { margin-left: auto; flex-shrink: 0; }
.selected-model-info { display: grid; gap: 5px; min-width: 0; }.selected-model-info strong { font-size: 13px; overflow-wrap: anywhere; font-weight: 500; }.selected-model-info span { color: #92a3be; font-size: 11px; }
.hub-notice { margin-top: 16px; font-size: 12px; }.hub-notice .n-button { margin-left: 12px; }
.hub-footnote { display: flex; align-items: start; gap: 7px; color: #7e8fa9; font-size: 11px; margin: 16px 0 0; line-height: 1.7; }.hub-footnote svg { margin-top: 2px; }
@media (max-width: 900px) { .hub-heading > .n-tag { display: none; } }
@media (max-width: 680px) { .hub-discovery { padding: 18px; }.hub-heading { align-items: start; gap: 12px; }.hub-heading h2 { font-size: 17px; }.hub-select-label { align-items: start; flex-direction: column; gap: 5px; }.hub-picker-row { flex-direction: column; }.hub-selection { padding: 12px; } }
</style>
