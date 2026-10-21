<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
import StudioIcon from '../shared/components/StudioIcon.vue'
const links = [
  { to: '/chat', icon: 'chat', label: '聊天' },
  { to: '/coding', icon: 'code', label: 'Coding' },
  { to: '/models', icon: 'cube', label: '模型库' },
  { to: '/image-studio', icon: 'image', label: '图片创作' },
  { to: '/audio-studio', icon: 'audio', label: '语音创作' },
  { to: '/settings', icon: 'settings', label: '设置' },
]
</script>
<template>
  <nav class="icon-rail" aria-label="主导航">
    <RouterLink to="/chat" class="rail-brand" aria-label="MLX Studio 首页">M</RouterLink>
    <RouterLink
      v-for="link in links"
      :key="link.to"
      class="rail-link"
      :class="{ selected: route.meta.navKey === link.to.slice(1) }"
      :to="link.to"
      :title="link.label"
      :aria-label="link.label"
      ><StudioIcon :name="link.icon" :size="21"
    /></RouterLink>
  </nav>
</template>
<style scoped>
.icon-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 16px 6px;
  color: var(--text-tertiary);
}
.rail-brand,
.rail-link {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  text-decoration: none;
}
.rail-brand {
  color: var(--text-primary);
  font-size: 22px;
  font-weight: 650;
  margin-bottom: 10px;
}
.rail-link:hover,
.rail-link.router-link-active,
.rail-link.selected {
  background: var(--surface-card);
  color: var(--text-primary);
}
@media (max-width: 680px) {
  .icon-rail {
    flex-direction: row;
    gap: 8px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--line);
  }
  .rail-brand {
    margin: 0 auto 0 0;
  }
}
</style>
