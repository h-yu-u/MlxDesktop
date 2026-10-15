<script setup lang="ts">
import { NButton, NDropdown } from 'naive-ui'
import { ref } from 'vue'
import StudioIcon from '../../../shared/components/StudioIcon.vue'

defineProps<{
  conversation: { id: string; title: string; pinned?: boolean }
  active: boolean
  disabled: boolean
}>()
const emit = defineEmits<{ open: []; rename: []; remove: []; pin: [] }>()
const menuOpen = ref(false)
const options = [
  { label: '重命名', key: 'rename' },
  { label: '删除', key: 'delete' },
]
function selectAction(key: string): void {
  if (key === 'rename') emit('rename')
  if (key === 'delete') emit('remove')
}
</script>

<template>
  <div
    class="conversation-row"
    :class="{ 'is-active': active, 'is-pinned': conversation.pinned, 'menu-open': menuOpen }"
  >
    <button
      class="conversation-title"
      :title="conversation.title"
      :aria-current="active ? 'true' : undefined"
      :disabled="disabled"
      @click="$emit('open')"
    >
      {{ conversation.title }}
    </button>
    <div class="conversation-actions">
      <NDropdown
        v-model:show="menuOpen"
        trigger="click"
        :options="options"
        :disabled="disabled"
        @select="selectAction"
      >
        <NButton
          quaternary
          circle
          size="tiny"
          :aria-label="`对话操作：${conversation.title}`"
          :aria-expanded="menuOpen"
          :disabled="disabled"
        >
          <StudioIcon name="more" :size="17" />
        </NButton>
      </NDropdown>
      <NButton
        quaternary
        circle
        size="tiny"
        :aria-label="`${conversation.pinned ? '取消置顶' : '置顶'}：${conversation.title}`"
        :title="conversation.pinned ? '取消置顶' : '置顶'"
        :aria-pressed="conversation.pinned === true"
        :disabled="disabled"
        class="pin-button"
        @click="$emit('pin')"
        ><StudioIcon name="pin" :size="17"
      /></NButton>
    </div>
  </div>
</template>

<style scoped src="./ConversationListItem.styles.css"></style>
