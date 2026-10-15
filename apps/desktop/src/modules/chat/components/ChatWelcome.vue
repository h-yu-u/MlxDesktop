<script setup lang="ts">
import StudioIcon from '../../../shared/components/StudioIcon.vue'

defineEmits<{ prompt: [value: string]; image: [value: string] }>()
</script>

<template>
  <section class="chat-welcome" aria-label="欢迎使用 MLX Studio">
    <h1>今天，我们来做点什么？</h1>
    <p>让灵感在你的设备上发生。</p>
    <div class="welcome-suggestions" aria-label="灵感提示">
      <button
        class="example-card"
        @click="$emit('image', '生成一张壮丽的山湖风景图，日落时分，雪山倒映在宁静的湖面上。')"
      >
        <StudioIcon name="image" :size="16" />创作一张图片
      </button>
      <button
        class="example-card"
        @click="$emit('prompt', '用 TypeScript 写一个斐波那契函数，并解释它的实现。')"
      >
        <StudioIcon name="code" :size="16" />帮我写代码
      </button>
      <button
        class="example-card"
        @click="$emit('prompt', '我有一个新想法，请通过提问帮我梳理思路。')"
      >
        <StudioIcon name="bolt" :size="16" />一起找灵感
      </button>
    </div>
  </section>
</template>

<style scoped src="./ChatWelcome.styles.css"></style>
