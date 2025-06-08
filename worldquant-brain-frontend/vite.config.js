// vite.config.js (或 vitest.config.js)
/// <reference types="vitest" />
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path'; // 确保导入 path 用于路径解析

export default defineConfig({
  plugins: [vue()],
  test: { // Vitest 配置
    globals: true, // 自动导入 describe, it, expect 等全局API
    environment: 'happy-dom', // 或 'jsdom', happy-dom 通常更快
    setupFiles: ['./src/tests/setup.js'], // 可选的测试全局配置文件路径
    coverage: { // 可选的覆盖率配置
      provider: 'v8', // 或 'istanbul'
      reporter: ['text', 'json', 'html'], // 输出报告的格式
      reportsDirectory: './src/tests/coverage', // 覆盖率报告输出目录
      all: true, // 是否计算所有被包含文件的覆盖率，即使它们没有被测试
      include: ['src/**/*.{js,vue}'], // 需要计算覆盖率的文件glob模式
      exclude: [ // 从覆盖率计算中排除的文件/目录glob模式
        'src/main.js',
        'src/router/index.js',
        'src/plugins/**',
        'src/assets/**',
        'src/tests/**', // 测试自身的设置文件
        '**/__tests__/**', // 测试文件本身
        '**/*.d.ts', // 类型定义文件
        'src/App.vue', // App.vue 通常是集成点，单元测试价值较低
        // 根据项目实际情况，可能还需排除其他如 constants, utils 等
      ],
    },
    alias: { // 配置路径别名，确保 Vitest 能解析如 @/components/... 的导入
      '@': path.resolve(__dirname, './src')
    },
    // Vitest 默认情况下会查找项目根目录下的 tsconfig.json 或 jsconfig.json 来解析路径。
    // 如果使用 TypeScript，确保 tsconfig.json 中的 paths 配置与此处的 alias 一致。
  },
});
