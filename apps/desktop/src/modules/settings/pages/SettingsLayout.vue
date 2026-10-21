<script setup lang="ts">
const links = [
  { to: '/settings', label: '概览' },
  { to: '/settings/coding', label: 'Coding' },
  { to: '/settings/extensions/skills', label: 'Skills' },
  { to: '/settings/extensions/mcp', label: 'MCP 服务' },
  { to: '/settings/extensions/builtin', label: '内置工具' },
  { to: '/settings/runtime', label: '运行与诊断' },
  { to: '/settings/privacy', label: '隐私与数据' },
]
</script>
<template>
  <div class="settings-layout">
    <nav aria-label="设置分类">
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        active-class=""
        exact-active-class="selected"
        >{{ link.label }}</RouterLink
      >
    </nav>
    <main class="settings-content"><RouterView /></main>
  </div>
</template>
<style scoped>
.settings-layout {
  display: grid;
  grid-template-columns: 176px minmax(0, 1fr);
  min-width: 0;
  min-height: 0;
  height: 100%;
}
nav {
  padding: 24px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--surface-sidebar);
}
nav a {
  padding: 10px 12px;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: var(--radius-control);
}
nav a.selected {
  background: var(--surface-hover);
  color: var(--text-primary);
}
.settings-content {
  padding: 24px;
  max-width: 920px;
  width: 100%;
  box-sizing: border-box;
  overflow-y: auto;
  min-width: 0;
}
.settings-content :deep(.page-content) {
  padding: 0;
}
@media (max-width: 820px) {
  .settings-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
  }
  nav {
    padding: 12px;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 4px;
  }
  .settings-content {
    padding: 16px;
  }
}
</style>
