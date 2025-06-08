<template>
  <!--
    根据路由元信息决定是否使用 MainLayout。
    如果路由的 meta.layout 设置为 'MainLayout' (或类似)，则使用 MainLayout。
    否则，直接渲染 router-view (例如登录页就不需要 MainLayout)。
    或者，更简单的方式是，MainLayout 内部处理 NavBar 和 SideBar 的显示逻辑，
    App.vue 始终只渲染 <router-view/>，而路由配置中，将 MainLayout 作为父路由组件。
    我们将采用后一种方法，因为它更符合 Vue Router 的嵌套路由设计。
  -->
  <router-view />
</template>

<script setup lang="ts">
// App.vue 通常不需要太多逻辑，主要作为路由的挂载点
</script>

<style>
/* 全局样式已在 DEV-020 中定义，这里可以保持不变或按需调整 */
html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif;
}

#app { /* Vite 项目的挂载点通常是 #app */
  height: 100%;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
}
</style>
