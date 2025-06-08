/* eslint-env node */
require('@rushstack/eslint-patch/modern-module-resolution');

module.exports = {
  root: true,
  extends: [
    'plugin:vue/vue3-essential', // Vue 3 核心规则
    'eslint:recommended',        // ESLint 推荐规则
    '@vue/eslint-config-typescript', // TypeScript 相关规则
    '@vue/eslint-config-prettier/skip-formatting' // Prettier 集成 (跳过格式化，让 Prettier 处理)
  ],
  parserOptions: {
    ecmaVersion: 'latest' // 使用最新的 ECMAScript 版本
  },
  rules: {
    // 在这里可以覆盖或添加特定的 ESLint 规则
    // 例如：'vue/multi-word-component-names': 'off', // 关闭组件名必须多词的规则
    'vue/no-unused-vars': 'warn', // 未使用的 Vue 变量警告
    'no-console': process.env.NODE_ENV === 'production' ? 'warn' : 'off', // 生产环境禁用 console
    'no-debugger': process.env.NODE_ENV === 'production' ? 'warn' : 'off', // 生产环境禁用 debugger
    // "prettier/prettier": ["warn", {}, { "usePrettierrc": true }] // 如果不用 skip-formatting，可以这样配置
  }
};
