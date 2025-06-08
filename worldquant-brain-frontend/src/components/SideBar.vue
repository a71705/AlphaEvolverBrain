<template>
  <!-- Element Plus 侧边栏容器 -->
  <el-aside width="200px" class="sidebar">
    <!-- Element Plus 导航菜单 -->
    <el-menu
      :default-active="activeMenu"
      class="el-menu-vertical-demo"
      router
      :collapse="isCollapsed"
    >
      <!-- 菜单项：实验列表 -->
      <el-menu-item index="/experiments">
        <el-icon><DataAnalysis /></el-icon> <!-- 使用 Element Plus 图标 -->
        <template #title>实验列表</template>
      </el-menu-item>

      <!-- 菜单项：数据源 (示例) -->
      <el-menu-item index="/data-sources">
        <el-icon><Coin /></el-icon>
        <template #title>数据源</template>
      </el-menu-item>

      <!-- 菜单项：系统状态 (示例) -->
      <el-menu-item index="/status">
        <el-icon><Monitor /></el-icon>
        <template #title>系统状态</template>
      </el-menu-item>

      <!-- 可以根据需要添加更多菜单项 -->
    </el-menu>
    <!-- 折叠按钮 (可选) -->
    <!--
    <div class="sidebar-toggle" @click="isCollapsed = !isCollapsed">
      <el-icon v-if="isCollapsed"><Expand /></el-icon>
      <el-icon v-else><Fold /></el-icon>
    </div>
    -->
  </el-aside>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRoute } from 'vue-router';
// 导入 Element Plus 图标
import {
  DataAnalysis,
  Coin,
  Monitor,
  // Expand, // 如果使用折叠功能
  // Fold,   // 如果使用折叠功能
} from '@element-plus/icons-vue';

const route = useRoute(); // 获取当前路由信息
const isCollapsed = ref(false); // 侧边栏折叠状态 (暂不启用完整折叠功能)

// 计算当前激活的菜单项，基于当前路由路径
const activeMenu = computed(() => route.path);

</script>

<style scoped>
.sidebar {
  background-color: #ffffff; /* 背景色 */
  border-right: 1px solid #e6e6e6; /* 右边框 */
  height: 100%; /* 占据父容器全部高度 */
  display: flex;
  flex-direction: column;
}

.el-menu-vertical-demo:not(.el-menu--collapse) {
  width: 200px; /* 菜单未折叠时的宽度 */
  min-height: 400px; /* 最小高度，可根据内容调整 */
  flex-grow: 1; /* 占据剩余空间 */
}
.el-menu {
  border-right: none; /* 移除 el-menu 自带的右边框，因为父级 asaide 已经有边框 */
}

/*
.sidebar-toggle {
  padding: 10px;
  text-align: center;
  cursor: pointer;
  border-top: 1px solid #e6e6e6;
}
*/
</style>
