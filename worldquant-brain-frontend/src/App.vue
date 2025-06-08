// src/App.vue
<template>
  <el-config-provider :locale="locale"> <!-- Element Plus 国际化配置 -->
    <div class="common-layout">
      <el-container v-if="isLoggedIn"> <!-- 只在登录后显示主布局 -->
        <NavBar /> <!-- 顶部导航栏 -->
        <el-container class="main-content-below-navbar">
          <SideBar /> <!-- 侧边栏 -->
          <el-main class="main-content-area">
            <router-view /> <!-- 路由视图，用于显示页面组件 -->
          </el-main>
        </el-container>
      </el-container>
      <router-view v-else /> <!-- 如果未登录，则只渲染路由视图 (例如登录页) -->
    </div>
  </el-config-provider>
</template>

<script>
import { computed } from 'vue';
import NavBar from './components/NavBar.vue';
import SideBar from './components/SideBar.vue';
import { ElConfigProvider } from 'element-plus';
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'; // 引入中文语言包

export default {
  name: 'App',
  components: {
    NavBar,
    SideBar,
    ElConfigProvider
  },
  setup() {
    // 计算属性判断用户是否登录
    const isLoggedIn = computed(() => {
      const token = localStorage.getItem('session_token');
      const expiresAt = localStorage.getItem('expires_at');
      if (token && expiresAt) {
        return new Date().getTime() < new Date(expiresAt).getTime();
      }
      return false;
    });

    return {
      isLoggedIn,
      locale: zhCn, // 设置 Element Plus 语言为中文
    };
  }
};
</script>

<style>
/* 全局样式 */
body {
  margin: 0; /* 移除 body 的默认 margin */
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', 'FAE\8F6F\96C5\9ED1', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.common-layout {
  height: 100vh; /* 应用容器占满整个视口高度 */
}

.main-content-below-navbar {
   height: calc(100vh - 60px); /* 计算导航栏以下区域的高度 */
   display: flex;
}

.main-content-area {
  padding: 20px; /* 主内容区域内边距 */
  background-color: #f0f2f5; /* 主内容区域背景色，可选 */
  height: 100%; /* 确保 main content area 填满剩余空间 */
  overflow-y: auto; /* 如果内容超出则显示滚动条 */
}

/* Element Plus 组件的全局样式调整 (如果需要) */
.el-header {
  padding: 0 !important; /* 覆盖 Element Plus header 的默认 padding */
}
.el-aside {
    overflow: hidden; /* 隐藏侧边栏内部的滚动条，由 .sidebar-aside 控制 */
}
.el-main {
    padding: 20px; /* 确保 main 区域有内边距 */
}
</style>
