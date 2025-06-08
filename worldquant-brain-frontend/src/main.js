// src/main.js
import { createApp } from 'vue';
import App from './App.vue';
import router from './router'; // 确保 router 文件存在且已配置
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
// 如果安装了图标库，也在这里引入
import * as ElementPlusIconsVue from '@element-plus/icons-vue';

const app = createApp(App);

app.use(router);
app.use(ElementPlus);

// 注册所有 Element Plus 图标 (如果已安装)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

app.mount('#app');
