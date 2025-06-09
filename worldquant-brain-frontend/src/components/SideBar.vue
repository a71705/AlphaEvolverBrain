// src/components/SideBar.vue
<template>
  <el-aside width="200px" class="sidebar-aside" v-if="isLoggedIn">
    <el-menu
      :default-active="activeIndex"
      class="el-menu-vertical-demo"
      router
      :collapse="isCollapsed"
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409EFF"
    >
      <!-- 菜单折叠按钮 -->
      <!-- <el-radio-group v-model="isCollapsed" style="margin-bottom: 20px;">
        <el-radio-button :label="false">展开</el-radio-button>
        <el-radio-button :label="true">收起</el-radio-button>
      </el-radio-group> -->

      <el-menu-item index="/experiments">
        <el-icon><DataAnalysis /></el-icon>
        <span>实验列表</span>
      </el-menu-item>
      <el-menu-item index="/data-sources" disabled> <!-- 暂时禁用 -->
        <el-icon><Coin /></el-icon>
        <span>数据源</span>
      </el-menu-item>
      <el-menu-item index="/status" disabled> <!-- 暂时禁用 -->
                <el-icon><DataLine /></el-icon> <!-- DEV-049: 更新图标 -->
                <span>API用量监控</span> <!-- DEV-049: 更新文本 -->
      </el-menu-item>
              <el-menu-item index="/compare-alphas">
                <el-icon><Histogram /></el-icon>
                <span>Alpha比较</span>
              </el-menu-item>
      <!-- 更多菜单项 -->
    </el-menu>
  </el-aside>
</template>

<script>
import { ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router'; // 确保从 vue-router 导入
import {
  DataAnalysis, // 实验列表图标
          Coin,
          Monitor,
          Histogram,
          DataLine,     // DEV-049: 新增图标导入
          // Menu as IconMenu,
        } from '@element-plus/icons-vue';

export default {
  name: 'SideBar',
  components: {
    DataAnalysis,
    Coin,
            Monitor,    // Monitor 现在可能不再直接使用，或者用于其他系统状态页面
            Histogram,
            DataLine,   // DEV-049
    // IconMenu
  },
  setup() {
    const route = useRoute();
    const router = useRouter(); // 添加router实例
    const isCollapsed = ref(false); // 控制菜单是否折叠，默认为 false (展开)
    const activeIndex = ref('/experiments'); // 默认激活的菜单项

    // 计算属性判断用户是否登录
    const isLoggedIn = computed(() => {
      const token = localStorage.getItem('session_token');
      const expiresAt = localStorage.getItem('expires_at');
      if (token && expiresAt) {
        return new Date().getTime() < new Date(expiresAt).getTime();
      }
      return false;
    });

    // 监听路由变化来更新 activeIndex，确保侧边栏高亮与当前路由匹配
    watch(() => route.path, (newPath) => {
      // 简单匹配，如果路由是 /experiments 或 /experiments/xxx，都高亮 /experiments
      if (newPath.startsWith('/experiments')) {
        activeIndex.value = '/experiments';
      } else if (newPath.startsWith('/data-sources')) {
        activeIndex.value = '/data-sources';
              } else if (newPath.startsWith('/status/api-usage')) { // DEV-049: 更新路径匹配
                activeIndex.value = '/status/api-usage';
              } else if (newPath.startsWith('/compare-alphas')) {
                activeIndex.value = '/compare-alphas';
      } else {
        activeIndex.value = newPath;
      }
            }, { immediate: true });

    // 如果未登录且尝试访问非公开页面，导航守卫会处理重定向
    // 这里确保未登录时侧边栏不渲染
    // 如果用户登出，isLoggedIn 会变为 false，侧边栏会消失
    watch(isLoggedIn, (loggedIn) => {
        if(!loggedIn && route.meta.requiresAuth) { // 检查路由是否需要认证
            router.push('/login');
        }
    });

    return {
      isCollapsed,
      isLoggedIn,
      activeIndex
    };
  }
};
</script>

<style scoped>
.sidebar-aside {
  background-color: #304156; /* 深色背景 */
  height: calc(100vh - 60px); /* 减去顶部导航栏的高度 */
  transition: width 0.28s; /* 折叠动画 */
  overflow-y: auto; /* 内容过多时显示滚动条 */
  overflow-x: hidden;
}
.el-menu {
  border-right: none; /* 移除 Element Plus 菜单默认的右边框 */
}
.el-menu-vertical-demo:not(.el-menu--collapse) {
  width: 200px; /* 展开时的宽度 */
  min-height: 400px; /* 最小高度 */
}
/* 可以添加折叠按钮的样式 */
</style>
