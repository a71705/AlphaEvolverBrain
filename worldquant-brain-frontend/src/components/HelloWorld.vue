<template>
  <div class="hello-world">
    <h1>{{ msg }}</h1>
    <p>
      这是一个占位符组件，用于演示项目结构。
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

// 定义 props
defineProps<{ msg: string }>();

// 示例响应式数据
const count = ref(0);
</script>

<style scoped>
/* scoped CSS 仅应用于当前组件 */
.hello-world {
  text-align: center;
  margin-top: 20px;
}
h1 {
  color: #42b983; /* Vue 绿色 */
}
</style>
