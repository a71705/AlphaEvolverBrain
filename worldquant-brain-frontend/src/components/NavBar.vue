// src/components/NavBar.vue
<template>
  <el-header class="navbar-header">
    <div class="logo-title-container">
      <!-- 您可以在这里放置一个 Logo 图片 -->
      <!-- <img src="@/assets/logo.png" alt="App Logo" class="app-logo"> -->
      <span class="app-title">WorldQuant Brain Alpha 进化系统</span>
    </div>
    <div class="navbar-menu">
      <el-dropdown v-if="isLoggedIn" @command="handleCommand">
        <span class="el-dropdown-link">
          用户<el-icon class="el-icon--right"><arrow-down /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <span v-else class="user-status">未登录</span>
    </div>
  </el-header>
</template>

<script>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus'; // 用于显示消息提示
import { ArrowDown } from '@element-plus/icons-vue'; // 导入图标

export default {
  name: 'NavBar',
  components: {
    ArrowDown // 注册图标组件
  },
  setup() {
    const router = useRouter();

    // 计算属性判断用户是否登录
    const isLoggedIn = computed(() => {
      const token = localStorage.getItem('session_token');
      const expiresAt = localStorage.getItem('expires_at');
      if (token && expiresAt) {
        return new Date().getTime() < new Date(expiresAt).getTime();
      }
      return false;
    });

    // 处理下拉菜单命令
    const handleCommand = (command) => {
      if (command === 'logout') {
        localStorage.removeItem('session_token');
        localStorage.removeItem('expires_at');
        ElMessage.success('您已成功退出登录');
        router.push('/login'); // 重定向到登录页
      }
    };

    return {
      isLoggedIn,
      handleCommand,
    };
  }
};
</script>

<style scoped>
.navbar-header {
  display: flex;
  justify-content: space-between; /* 两端对齐 */
  align-items: center; /* 垂直居中 */
  padding: 0 20px; /* 左右内边距 */
  background-color: #409EFF; /* Element Plus 主题蓝 */
  color: white; /* 文字颜色 */
  height: 60px; /* 导航栏高度 */
}

.logo-title-container {
  display: flex;
  align-items: center;
}

.app-logo {
  height: 40px; /* Logo 高度 */
  margin-right: 10px; /* Logo 和标题间距 */
}

.app-title {
  font-size: 1.2em; /* 应用标题字体大小 */
  font-weight: bold;
}

.navbar-menu {
  display: flex;
  align-items: center;
}

.el-dropdown-link {
  cursor: pointer;
  color: white; /* 下拉菜单文字颜色 */
  display: flex;
  align-items: center;
}
.user-status {
  font-size: 0.9em;
}
</style>
