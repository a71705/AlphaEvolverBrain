// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router';
import LoginView from '../views/LoginView.vue';
import HomeView from '../views/HomeView.vue';
// ExperimentListView.vue is now lazy-loaded, so explicit import is not needed here.
// import ExperimentListView from '../views/ExperimentListView.vue';
import ExperimentDetailView from '../views/ExperimentDetailView.vue'; // 导入新视图

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: { requiresAuth: true } // 假设首页也需要登录
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView
  },
  {
    path: '/about', // 假设 about 页面是公开的，或者也需要 requiresAuth
    name: 'about',
    component: () => import(/* webpackChunkName: "about" */ '../views/AboutView.vue')
    // meta: { requiresAuth: true } // 如果 about 页面需要登录
  },
  {
    path: '/experiments',
    name: 'experiments',
    // 在 DEV-022 中我们使用了动态导入，这里保持一致
    component: () => import(/* webpackChunkName: "experiments" */ '../views/ExperimentListView.vue'),
    meta: { requiresAuth: true } // 确保此路由需要认证
  },
  { // 新增实验详情页路由
    path: '/experiments/:experimentId', // 使用动态路由参数
    name: 'experiment-detail',
    component: ExperimentDetailView, // 指向新创建的视图组件
    meta: { requiresAuth: true } // 需要认证才能访问
  }
  // ... 其他路由
];

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
});

// 全局前置导航守卫 (来自 DEV-021, adjusted as per task description)
router.beforeEach((to, from, next) => {
  const publicPages = ['/login'];
  // 路由是否明确标记需要认证
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth);

  // 检查 token 是否存在且未过期
  const loggedIn = (() => {
    const token = localStorage.getItem('session_token');
    const expiresAt = localStorage.getItem('expires_at');
    if (!token || !expiresAt) return false;
    return new Date().getTime() < new Date(expiresAt).getTime();
  })();

  if (requiresAuth && !loggedIn) {
    // 如果需要认证但未登录 (或 token 过期)，重定向到登录页
    // 清理可能已过期的 token
    if (!loggedIn && (localStorage.getItem('session_token') || localStorage.getItem('expires_at'))) {
        localStorage.removeItem('session_token');
        localStorage.removeItem('expires_at');
    }
    return next({
      path: '/login',
      query: { redirect: to.fullPath } // 保存原始目标路径
    });
  }

  if (loggedIn && to.path === '/login') {
    // 如果已登录且目标是登录页，重定向到首页或实验列表页
    return next('/experiments'); // 或 '/'
  }

  next(); // 正常导航
});

export default router;
