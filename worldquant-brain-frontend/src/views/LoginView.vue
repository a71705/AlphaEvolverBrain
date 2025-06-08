// src/views/LoginView.vue
<template>
  <div class="login-container">
    <!-- 使用 Element Plus 表单组件 -->
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <span>用户登录 - WorldQuant Brain Alpha 系统</span>
        </div>
      </template>
      <el-form @submit.prevent="handleLogin" :model="loginForm" :rules="rules" ref="loginFormRef" label-width="80px">
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="loginForm.email" placeholder="请输入邮箱"></el-input>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" show-password></el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="submitForm('loginFormRef')" :loading="loading">登录</el-button>
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false"></el-alert>
      </el-form>
    </el-card>
  </div>
</template>

<script>
import axios from 'axios'; // 确保 axios 已安装
import { ref, reactive } from 'vue';
import { useRouter } from 'vue-router'; // 导入 useRouter

export default {
  name: 'LoginView',
  setup() {
    const router = useRouter(); // 获取 router 实例
    const loginFormRef = ref(null); // 表单引用
    const loginForm = reactive({
      email: '',
      password: '',
    });
    const loading = ref(false); // 加载状态
    const error = ref(''); // 错误信息

    // 表单验证规则
    const rules = reactive({
      email: [
        { required: true, message: '请输入邮箱地址', trigger: 'blur' },
        { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }
      ],
      password: [
        { required: true, message: '请输入密码', trigger: 'blur' },
        { min: 6, message: '密码长度不能少于6位', trigger: 'blur' } // 假设密码最小长度为6
      ]
    });

    const submitForm = (formName) => {
      loginFormRef.value.validate((valid) => {
        if (valid) {
          handleLogin();
        } else {
          console.log('表单验证失败!');
          return false;
        }
      });
    };

    const handleLogin = async () => {
      loading.value = true;
      error.value = ''; // 清除之前的错误
      try {
        // 后端 API 地址，根据实际情况调整
        // 在实际项目中, API URL 应该配置在环境变量或一个单独的配置文件中
        const apiUrl = process.env.VUE_APP_API_BASE_URL ? `${process.env.VUE_APP_API_BASE_URL}/api/v1/auth/login` : '/api/v1/auth/login';

        const response = await axios.post(apiUrl, {
          email: loginForm.email,
          password: loginForm.password
        });

        if (response.data && response.data.session_token) {
          localStorage.setItem('session_token', response.data.session_token);
          localStorage.setItem('expires_at', response.data.expires_at);
          // 登录成功后跳转到实验列表页
          router.push('/experiments');
        } else {
          // 如果后端成功响应但数据格式不符合预期
          error.value = '登录失败：无效的响应数据。';
        }
      } catch (err) {
        if (err.response && err.response.data && err.response.data.detail) {
          error.value = `登录失败：${err.response.data.detail}`;
        } else if (err.request) {
          error.value = '登录失败：无法连接到服务器，请检查网络。';
        } else {
          error.value = `登录失败：${err.message}`;
        }
        console.error('登录请求失败:', err);
      } finally {
        loading.value = false;
      }
    };

    return {
      loginFormRef,
      loginForm,
      rules,
      loading,
      error,
      submitForm,
      handleLogin // 暴露 handleLogin 以便 @submit.prevent 调用 (虽然现在是通过 submitForm)
    };
  }
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 90vh; /* 使容器至少占据视口高度的90% */
  background-color: #f0f2f5; /* 可选：添加背景色 */
}
.login-card {
  width: 450px; /* 登录卡片的宽度 */
}
.card-header {
  text-align: center;
  font-size: 1.5em; /* 头部字体大小 */
}
.el-alert {
  margin-top: 15px; /* 错误提示与表单项的间距 */
}
</style>
