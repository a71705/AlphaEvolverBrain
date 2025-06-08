<template>
  <!-- Element Plus 头部容器 -->
  <el-header class="navbar">
    <div class="logo-area">
      <!-- Logo 或应用名称 -->
      <router-link to="/" class="logo-link">
        <span>Alpha Evolution</span>
      </router-link>
    </div>
    <div class="spacer"></div> <!-- 占位符，将右侧内容推到最右边 -->
    <div class="user-actions">
      <!-- 根据认证状态显示不同内容 -->
      <template v-if="isAuthenticated">
        <el-dropdown @command="handleCommand">
          <span class="el-dropdown-link">
            欢迎您 <!-- 可以显示用户名，如果获取到的话 -->
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <!-- 未登录时，可以显示登录按钮 -->
        <el-button type="primary" @click="goToLogin" size="small">登 录</el-button>
      </template>
    </div>
  </el-header>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus'; // 导入 Element Plus 消息提示组件
import { ArrowDown } from '@element-plus/icons-vue'; // 导入 Element Plus 图标

const router = useRouter();
const route = useRoute(); // 获取当前路由信息
const isAuthenticated = ref(false); // 初始化认证状态

// 检查认证状态的函数
const checkAuthStatus = () => {
  const token = localStorage.getItem('session_token');
  const expiresAt = localStorage.getItem('expires_at');
  if (token && expiresAt) {
    isAuthenticated.value = new Date(expiresAt) > new Date();
  } else {
    isAuthenticated.value = false;
  }
};

// 组件挂载时检查认证状态
onMounted(() => {
  checkAuthStatus();
  // 监听 localStorage 变化，以便在其他标签页登出时同步状态 (较复杂，暂不实现)
  // window.addEventListener('storage', checkAuthStatus);
});

// 监听路由变化，以在用户通过非常规方式改变认证状态后（例如手动清除localStorage后刷新）更新UI
watch(() => route.path, () => {
  checkAuthStatus();
});


// 处理下拉菜单命令
const handleCommand = (command: string) => {
  if (command === 'logout') {
    // 退出登录逻辑
    ElMessageBox.confirm('您确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      localStorage.removeItem('session_token');
      localStorage.removeItem('expires_at');
      isAuthenticated.value = false; // 更新认证状态
      ElMessage.success('您已成功退出登录！');
      router.push('/login'); // 重定向到登录页
    }).catch(() => {
      // 用户取消操作
    });
  } else if (command === 'profile') {
    ElMessage.info('个人中心功能正在开发中...');
    // router.push('/profile'); // 跳转到个人中心页
  }
};

// 跳转到登录页
const goToLogin = () => {
  router.push('/login');
};
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center; /* 垂直居中对齐子元素 */
  padding: 0 20px; /* 左右内边距 */
  background-color: #ffffff; /* 背景色 */
  border-bottom: 1px solid #e6e6e6; /* 底部边框 */
  height: 60px; /* 固定高度 */
}

.logo-area {
  font-size: 20px;
  font-weight: bold;
}
.logo-link {
  text-decoration: none; /* 移除链接下划线 */
  color: #303133; /* Logo 颜色 */
}


.spacer {
  flex-grow: 1; /* 占据所有剩余空间 */
}

.user-actions {
  display: flex;
  align-items: center;
}

.el-dropdown-link {
  cursor: pointer; /* 鼠标指针样式 */
  color: var(--el-color-primary); /* Element Plus 主题色 */
  display: flex;
  align-items: center;
}
</style>
