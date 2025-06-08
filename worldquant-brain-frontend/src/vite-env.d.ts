/// <reference types="vite/client" />

// 如果需要扩展 Vite 的环境变量类型，可以在这里添加
// 例如：
// interface ImportMetaEnv {
//   readonly VITE_APP_TITLE: string
//   // 更多环境变量...
// }

// interface ImportMeta {
//   readonly env: ImportMetaEnv
// }

// 为 .vue 文件提供 TypeScript 类型支持
declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<{}, {}, any>;
  export default component;
}
