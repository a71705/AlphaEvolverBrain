<template>
  <div class="login-container">
    <!-- Element Plus 表单容器 -->
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <span>系统登录</span>
        </div>
      </template>
      <!-- 登录表单 -->
      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        label-width="80px"
        @submit.prevent="handleLogin"
      >
        <!-- 邮箱输入框 -->
        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model="loginForm.email"
            placeholder="请输入邮箱地址"
            clearable
          />
        </el-form-item>
        <!-- 密码输入框 -->
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
            clearable
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <!-- 登录按钮 -->
        <el-form-item>
          <el-button
            type="primary"
            @click="handleLogin"
            :loading="loading"
            class="login-button"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>
      <!-- 错误提示 -->
      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
        class="error-alert"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'; // 导入 Vue 3组合式 API
import { useRouter } from 'vue-router'; // 导入 Vue Router
import axios from 'axios'; // 导入 Axios 用于 HTTP 请求
import type { FormInstance, FormRules } from 'element-plus'; // 导入 Element Plus 表单类型

// 获取路由实例
const router = useRouter();

// 登录表单的响应式数据模型
const loginForm = reactive({
  email: '',
  password: '',
});

// 加载状态
const loading = ref(false);
// 错误信息
const errorMessage = ref('');

// Element Plus 表单实例引用
const loginFormRef = ref<FormInstance>();

// 表单验证规则
const loginRules = reactive<FormRules>({
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: ['blur', 'change'] },
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
});

// 处理登录逻辑的异步函数
const handleLogin = async () => {
  if (!loginFormRef.value) return; // 确保表单实例存在
  try {
    // 验证表单
    await loginFormRef.value.validate();
    loading.value = true; // 开始加载状态
    errorMessage.value = ''; // 清除之前的错误信息

    // 发送登录请求到后端 API
    const response = await axios.post('/api/v1/auth/login', {
      email: loginForm.email,
      password: loginForm.password,
    });

    // 检查后端返回的数据结构是否符合预期
    if (response.data && response.data.session_token && response.data.expires_at) {
      // 登录成功，存储 session_token 和 expires_at 到 localStorage
      localStorage.setItem('session_token', response.data.session_token);
      localStorage.setItem('expires_at', response.data.expires_at);

      // 登录成功后，重定向到实验列表页面
      router.push('/experiments');
    } else {
      // 后端返回数据结构不符合预期
      errorMessage.value = '登录失败：无效的服务器响应。';
      console.error('Login failed: Invalid server response structure', response.data);
    }
  } catch (error: any) {
    // 处理登录失败的情况
    if (axios.isAxiosError(error) && error.response) {
      // 从后端获取错误信息
      errorMessage.value = error.response.data.detail || '登录失败，请检查您的凭据。';
    } else if (error instanceof Error && error.message.includes('validate')) {
      // 表单验证失败的提示可以由 Element Plus 自动处理，这里也可以选择不设置通用错误信息
      console.log('Form validation failed');
    }
    else {
      // 其他未知错误
      errorMessage.value = '登录时发生未知错误。';
      console.error('Login error:', error);
    }
  } finally {
    loading.value = false; // 结束加载状态
  }
};
</script>

<style scoped>
/* Login.vue 组件的特定样式 */
.login-container {
  display: flex; /* 使用 Flexbox 布局 */
  justify-content: center; /* 水平居中 */
  align-items: center; /* 垂直居中 */
  min-height: 100vh; /* 最小高度为视口高度，确保全屏居中 */
  background-color: #f0f2f5; /* 设置背景颜色 */
}

.login-card {
  width: 400px; /* 设置登录卡片的宽度 */
  padding: 20px; /* 内边距 */
}

.card-header {
  text-align: center; /* 头部文本居中 */
  font-size: 20px; /* 头部字体大小 */
  font-weight: bold; /* 字体加粗 */
}

.login-button {
  width: 100%; /* 登录按钮宽度占满父容器 */
}

.error-alert {
  margin-top: 15px; /* 错误提示与表单的间距 */
}
</style>
