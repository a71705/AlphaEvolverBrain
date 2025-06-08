<template>
  <div class="not-found-page">
    <el-result
      icon="error"
      title="404 - 页面未找到"
      sub-title="抱歉，您访问的页面不存在或已被移除。"
    >
      <template #extra>
        <el-button type="primary" @click="goHome">返回首页</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
const router = useRouter();
const goHome = () => {
  router.push('/');
};
</script>

<style scoped>
.not-found-page {
  display: flex;
  justify-content: center;
  align-items: center;
  height: calc(100vh - 120px); /* 减去可能的头部和底部空间 */
}
</style>
