import { createRouter, createWebHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';
import MainLayout from '@/layouts/MainLayout.vue';

const routes: Array<RouteRecordRaw> = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/experiments',
    children: [
      {
        path: 'experiments',
        name: 'experiments', // 实验列表页的路由名称
        component: () => import('../views/ExperimentList.vue'),
        meta: { requiresAuth: true, title: '实验列表' }
      },
      {
        // 实验详情页路由 (DEV-029 将实现此页面)
        path: 'experiments/:experimentId', // 使用路径参数 experimentId
        name: 'experiment-detail',        // 路由名称，与 ExperimentList.vue 中使用的对应
        component: () => import('../views/PlaceholderPage.vue'), // DEV-029 会替换为 ExperimentDetail.vue
        meta: { requiresAuth: true, title: '实验详情' } // 需要认证
      },
      {
        path: 'data-sources',
        name: 'data-sources',
        component: () => import('../views/PlaceholderPage.vue'),
        meta: { requiresAuth: true, title: '数据源' }
      },
      {
        path: 'status',
        name: 'status',
        component: () => import('../views/PlaceholderPage.vue'),
        meta: { requiresAuth: true, title: '系统状态' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/NotFoundPage.vue'),
  }
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

router.beforeEach((to, from, next) => {
  const requiresAuth = to.meta.requiresAuth;
  const token = localStorage.getItem('session_token');
  const expiresAt = localStorage.getItem('expires_at');
  let isAuthenticated = false;

  if (token && expiresAt) {
    isAuthenticated = new Date(expiresAt) > new Date();
    if (!isAuthenticated) {
      localStorage.removeItem('session_token');
      localStorage.removeItem('expires_at');
    }
  }

  // 设置页面标题
  const pageTitle = to.meta.title ? `${to.meta.title} - Alpha Evolution` : 'Alpha Evolution';
  if (document.title !== pageTitle) { // 避免不必要的 title 修改
      document.title = pageTitle;
  }

  if (requiresAuth && !isAuthenticated) {
    next({ name: 'login', query: { redirect: to.fullPath } });
  } else if (to.name === 'login' && isAuthenticated) {
    next({ name: 'experiments' });
  } else {
    next();
  }
});

export default router;
