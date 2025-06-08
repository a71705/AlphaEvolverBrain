import { createApp } from 'vue'; // 导入 createApp 用于创建 Vue 应用实例
import ElementPlus from 'element-plus'; // 导入 Element Plus UI 框架
import 'element-plus/dist/index.css'; // 导入 Element Plus 的全局 CSS 样式
import App from './App.vue'; // 导入根组件 App.vue
import router from './router'; // 导入路由配置

// 创建 Vue 应用实例
const app = createApp(App);

// 全局注册 Element Plus
app.use(ElementPlus);
// 全局注册 Vue Router
app.use(router);

// 将应用实例挂载到 HTML 页面中 ID 为 'app' 的元素上
app.mount('#app');
