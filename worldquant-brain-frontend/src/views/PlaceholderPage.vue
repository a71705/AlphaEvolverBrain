<template>
  <div class="placeholder-page">
    <h2>{{ $route.meta.title || '页面正在建设中' }}</h2>
    <p>此功能页面正在积极开发中，敬请期待！</p>
    <el-empty :description="($route.meta.title || '页面') + '正在建设中'" />
  </div>
</template>

<script setup lang="ts">
// 无特定脚本
</script>

<style scoped>
.placeholder-page {
  padding: 20px;
  text-align: center;
}
</style>
