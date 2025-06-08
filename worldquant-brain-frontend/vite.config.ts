import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // 配置开发服务器端口 (可选)
  server: {
    port: 8080, // 与文档中一致的端口
    open: true // 自动打开浏览器 (开发时可选)
  },
  // 配置 CSS 预处理器 (SASS)
  css: {
    preprocessorOptions: {
      scss: {
        // additionalData: \`@import "@/assets/styles/variables.scss";\` // 例如全局 SASS 变量
      }
    }
  }
});
