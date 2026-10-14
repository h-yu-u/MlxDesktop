<script setup lang="ts">
import StudioIcon from '../../../shared/components/StudioIcon.vue'
import alpineLake from '../assets/alpine-lake.svg'
import studioCat from '../assets/studio-cat.svg'

defineEmits<{ prompt: [value: string]; image: [value: string] }>()
const features = [
  { icon: 'bolt', title: '完全本地运行', detail: '数据安全，隐私无忧' },
  { icon: 'monitor', title: '支持多模态', detail: '文本 · 图像 · 生成' },
  { icon: 'tool', title: '简单易用', detail: '为创作者而生' },
]
</script>

<template>
  <section
    class="chat-welcome"
    aria-label="欢迎使用 MLX Studio"
  >
    <div class="welcome-intro">
      <span class="brand-mark welcome-mark">M</span>
      <h1>你好，我是 MLX Studio</h1>
      <p>在你的设备上，运行强大的 AI 模型</p>
    </div>
    <div class="welcome-features">
      <div
        v-for="feature in features"
        :key="feature.title"
        class="feature-card"
      >
        <StudioIcon
          :name="feature.icon"
          :size="30"
        />
        <div><strong>{{ feature.title }}</strong><small>{{ feature.detail }}</small></div>
      </div>
    </div>
    <div class="welcome-examples">
      <div class="examples-heading">
        试试这些示例 <StudioIcon
          name="arrow"
          :size="17"
        />
      </div>
      <div class="example-grid">
        <button
          class="example-card"
          @click="$emit('image', '生成一张壮丽的山湖风景图，日落时分，雪山倒映在宁静的湖面上。')"
        >
          <img
            :src="alpineLake"
            alt="日落时分的雪山与湖泊插画"
          >
          <span>生成一张壮丽的山湖风景图 <StudioIcon
            name="arrow"
            :size="16"
          /></span>
        </button>
        <button
          class="example-card"
          @click="$emit('prompt', '用 TypeScript 写一个斐波那契函数，并解释它的实现。')"
        >
          <div
            class="code-preview"
            aria-hidden="true"
          >
            <span class="code-comment">// 把想法变成代码</span><br><span class="code-purple">function</span> <span class="code-mint">fibonacci</span>(n: <span class="code-purple">number</span>) {<br>&nbsp; <span class="code-purple">if</span> (n &lt;= 1) <span class="code-purple">return</span> n<br>&nbsp; <span class="code-purple">return</span> fibonacci(n - 1)<br>&nbsp;&nbsp;&nbsp; + fibonacci(n - 2)<br>}
          </div>
          <span>写一个斐波那契函数 <StudioIcon
            name="arrow"
            :size="16"
          /></span>
        </button>
        <button
          class="example-card"
          @click="$emit('image', '生成一张可爱的猫咪图片，柔软的奶油色长毛猫，温暖的窗边光线。')"
        >
          <img
            :src="studioCat"
            alt="窗边的奶油色猫咪插画"
          >
          <span>生成一张可爱的猫咪图片 <StudioIcon
            name="arrow"
            :size="16"
          /></span>
        </button>
      </div>
    </div>
  </section>
</template>
