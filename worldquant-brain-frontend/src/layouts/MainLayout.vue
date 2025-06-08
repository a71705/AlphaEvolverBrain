<template>
  <!-- Element Plus 容器布局 -->
  <el-container class="main-layout">
    <!-- 侧边栏 -->
    <SideBar v-if="isAuthenticated" /> <!-- 仅在认证后显示侧边栏 -->

    <!-- 主内容区容器 -->
    <el-container :class="{ 'content-container-full': !isAuthenticated }">
      <!-- 头部导航栏 -->
      <NavBar />

      <!-- 主内容区 -->
      <el-main class="main-content">
        <router-view /> <!-- 子路由的视图将在这里渲染 -->
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import NavBar from '@/components/NavBar.vue'; // 导入头部导航栏组件
import SideBar from '@/components/SideBar.vue'; // 导入侧边栏组件

const route = useRoute();
const isAuthenticated = ref<boolean>(false); // Explicitly type here

const checkAuthStatus = () => {
  const token = localStorage.getItem('session_token');
  const expiresAt = localStorage.getItem('expires_at');
  // Ensure the expression always evaluates to a boolean
  isAuthenticated.value = !!(token && expiresAt && new Date(expiresAt).getTime() > new Date().getTime());
};

onMounted(checkAuthStatus);
// 监听路由变化，确保在导航到登录页后，如果 MainLayout 仍然是父级，能正确更新 isAuthenticated
watch(() => route.path, () => {
  checkAuthStatus();
});

</script>

<style scoped>
.main-layout {
  height: 100vh; /* 布局占据整个视口高度 */
  background-color: #f0f2f5; /* 主背景色 */
}

.content-container-full {
  /* 当没有侧边栏时（例如登录页），让内容容器占据全部宽度 */
   width: 100%;
}

.main-content {
  padding: 20px; /* 主内容区内边距 */
  background-color: #ffffff; /* 内容区背景通常为白色 */
  /* overflow-y: auto; */ /* 如果内容超长，允许垂直滚动 */
}
</style>
