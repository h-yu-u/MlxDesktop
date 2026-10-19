<script setup lang="ts">
import { useRoute } from 'vue-router'
import { TextAssistant } from '../../../capabilities/extensions'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { NAlert, NButton, NTabPane, NTabs } from 'naive-ui'
import { useAudioStudioStore } from '../stores/audio-studio.store'
import SpeechEditor from '../components/SpeechEditor.vue'
import AudioPlayer from '../components/AudioPlayer.vue'
import VoiceLibrary from '../components/VoiceLibrary.vue'
import AudioHistory from '../components/AudioHistory.vue'
import { runtimeConnectionStatus } from '../../../platform/runtime-bridge'
import type { AudioArtifact } from '../application/ports'
const store = useAudioStudioStore()
const tab = ref('create')
let reconnect = false
const route = useRoute()
onMounted(async () => {
  await store.loadWorkspace()
  const id = route.query.artifactId
  if (typeof id === 'string') await store.select(id)
})
onUnmounted(store.dispose)
watch(runtimeConnectionStatus, (status) => {
  if (status !== 'ready') {
    reconnect = true
    store.dispose()
  } else if (reconnect) {
    reconnect = false
    void store.loadWorkspace()
  }
})
function select(id: string): void {
  tab.value = 'create'
  void store.select(id)
}
function reuse(item: AudioArtifact): void {
  store.reuse(item)
  tab.value = 'create'
}
</script>
<template>
  <section class="page-content audio-page">
    <div class="audio-heading">
      <div>
        <h1 class="page-title">语音创作</h1>
        <p class="page-subtitle">用文字表达，让熟悉的声音讲述。</p>
      </div>
      <RouterLink to="/models"><NButton>管理语音模型</NButton></RouterLink>
    </div>
    <NAlert v-if="store.error" type="error" class="audio-notice">{{ store.error }}</NAlert>
    <NAlert v-if="store.loading" type="info" class="audio-notice">正在读取模型、音色与作品…</NAlert>
    <NTabs v-model:value="tab" type="line" animated>
      <NTabPane name="create" tab="创作">
        <NAlert v-if="!store.speechModels.length" type="info" class="audio-notice"
          >没有支持此模式的完整语音模型，请在模型库下载或导入 Qwen3-TTS Base / CustomVoice。</NAlert
        >
        <TextAssistant
          workspace="audio"
          :text="store.form.text"
          :disabled="store.busy || store.submitting"
          @apply="store.form = { ...store.form, text: $event }"
        />
        <div class="audio-creation">
          <SpeechEditor
            v-model:form="store.form"
            :models="store.speechModels"
            :voices="store.voices"
            :locked="store.busy || store.submitting"
            :submitting="store.submitting"
            @generate="store.generate"
            @library="tab = 'voices'"
          />
          <AudioPlayer
            :artifact="store.selectedArtifact"
            :url="store.selectedId ? store.urls[store.selectedId] : undefined"
            :job="store.activeJob"
            :busy="store.busy"
            :cancelling="store.cancelling"
            :saving="!!store.savingId"
            :sync-error="store.syncError"
            @cancel="store.cancel"
            @save="store.selectedId && store.save(store.selectedId)"
            @reuse="store.selectedArtifact && store.reuse(store.selectedArtifact)"
            @retry="store.selectedId && store.select(store.selectedId)"
            @reconnect="store.refreshJob"
          />
        </div>
      </NTabPane>
      <NTabPane name="voices" tab="音色库">
        <VoiceLibrary
          v-model:form="store.library.form"
          v-model:consent="store.library.consent"
          :reference="store.library.reference"
          :voices="store.voices"
          :loose-references="store.library.looseReferences"
          :urls="store.library.urls"
          :busy="store.library.busy"
          :error="store.library.error"
          :cleanup-error="store.library.cleanupError"
          @upload="store.library.upload"
          @save="store.library.save"
          @preview="store.library.preview"
          @update="store.library.update"
          @remove="store.library.remove"
          @cleanup="store.library.retryCleanup"
          @remove-reference="store.library.removeReference"
        />
      </NTabPane>
      <NTabPane name="works" tab="作品">
        <AudioHistory
          :artifacts="store.artifacts"
          :loading="store.historyLoading"
          :has-more="store.hasMore"
          :busy="store.busy"
          @select="select"
          @reuse="reuse"
          @save="store.save"
          @remove="store.remove"
          @more="store.loadHistory(false)"
          @refresh="store.loadHistory(true)"
        />
      </NTabPane>
    </NTabs>
  </section>
</template>
<style scoped>
.audio-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 22px;
}
.audio-creation {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(320px, 1fr);
  gap: 20px;
  align-items: start;
}
.audio-notice {
  margin-bottom: 16px;
}
@media (max-width: 960px) {
  .audio-creation {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 680px) {
  .audio-heading {
    align-items: start;
    flex-direction: column;
  }
}
</style>
