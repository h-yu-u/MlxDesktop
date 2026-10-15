<script setup lang="ts">
defineProps<{ title: string; subtitle: string }>()
</script>
<template>
  <header class="page-header">
    <div>
      <h1 class="page-title">
        {{ title }}
      </h1>
      <p class="page-subtitle">
        {{ subtitle }}
      </p>
    </div>
    <slot name="actions" />
  </header>
</template>
<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.page-subtitle {
  margin-bottom: 0;
}
@media (max-width: 680px) {
  .page-header {
    align-items: start;
  }
}
</style>
