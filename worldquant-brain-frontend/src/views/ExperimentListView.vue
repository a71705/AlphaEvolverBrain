// src/views/ExperimentListView.vue
<template>
  <div class="experiment-list-container">
    <el-card class="box-card">
      <template #header>
        <div class="clearfix">
          <span class="header-title">实验列表</span>
          <!-- 未来可以添加创建实验的按钮 -->
          <!-- <el-button style="float: right; padding: 3px 0" type="text">创建新实验</el-button> -->
        </div>
      </template>

      <div v-if="loading" v-loading="loading" class="loading-spinner" element-loading-text="正在加载实验数据...">
        <!-- 加载状态显示 -->
      </div>

      <el-table
        v-if="!loading && experiments.length > 0"
        :data="experiments"
        style="width: 100%"
        border
        empty-text="暂无实验数据"
      >
        <el-table-column prop="name" label="实验名称" sortable width="250">
          <template #default="scope">
            <router-link :to="`/experiments/${scope.row.id}`" class="experiment-name-link">
              {{ scope.row.name }}
            </router-link>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)">
              {{ scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_time" label="开始时间" sortable width="200">
          <template #default="scope">
            {{ formatDateTime(scope.row.start_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" show-overflow-tooltip>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="scope">
            <el-button
              size="small"
              type="primary"
              @click="viewDetails(scope.row.id)"
            >
              查看详情
            </el-button>
            <!-- 更多操作按钮，例如：删除、重新运行等 -->
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && experiments.length === 0" description="当前没有实验记录"></el-empty>

      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" style="margin-top: 20px;"></el-alert>

    </el-card>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import axios from 'axios';
import { useRouter } from 'vue-router'; // 导入 useRouter
import { ElMessage } from 'element-plus'; // 用于显示消息

export default {
  name: 'ExperimentListView',
  setup() {
    const router = useRouter(); // 获取 router 实例
    const experiments = ref([]);
    const loading = ref(false);
    const error = ref('');

    // 获取实验数据的方法
    const fetchExperiments = async () => {
      loading.value = true;
      error.value = '';
      try {
        const apiUrl = process.env.VUE_APP_API_BASE_URL ? `${process.env.VUE_APP_API_BASE_URL}/api/v1/experiments` : '/api/v1/experiments';
        const response = await axios.get(apiUrl, {
          headers: {
            // 如果需要认证，从 localStorage 获取 token
            // 'Authorization': `Bearer ${localStorage.getItem('session_token')}`
          }
        });
        if (response.data) {
          experiments.value = response.data;
        } else {
          experiments.value = []; // 确保在没有数据时为空数组
        }
      } catch (err) {
        console.error('获取实验列表失败:', err);
        if (err.response && err.response.data && err.response.data.detail) {
          error.value = `获取实验列表失败：${err.response.data.detail}`;
        } else if (err.request) {
          error.value = '获取实验列表失败：无法连接到服务器。';
        } else {
          error.value = `获取实验列表失败：${err.message}`;
        }
        ElMessage.error(error.value); // 使用 Element Plus 消息提示
        experiments.value = []; // 出错时也确保为空数组
      } finally {
        loading.value = false;
      }
    };

    // 组件挂载后获取数据
    onMounted(() => {
      fetchExperiments();
    });

    // 格式化日期时间
    const formatDateTime = (dateTimeString) => {
      if (!dateTimeString) return 'N/A';
      const date = new Date(dateTimeString);
      return date.toLocaleString('zh-CN', { hour12: false });
    };

    // 根据实验状态返回 Element Plus Tag 的类型
    const getStatusTagType = (status) => {
      switch (status) {
        case 'PENDING': return 'info';
        case 'RUNNING': return ''; // 默认 primary
        case 'COMPLETED': return 'success';
        case 'FAILED': return 'danger';
        case 'CANCELLED': return 'warning';
        default: return 'info';
      }
    };

    // 查看详情的导航方法
    const viewDetails = (experimentId) => {
      router.push(`/experiments/${experimentId}`);
    };

    return {
      experiments,
      loading,
      error,
      fetchExperiments,
      formatDateTime,
      getStatusTagType,
      viewDetails,
    };
  }
};
</script>

<style scoped>
.experiment-list-container {
  padding: 20px;
}
.box-card {
  /* 卡片样式可以根据需要调整 */
}
.header-title {
  font-size: 1.5em;
  font-weight: bold;
}
.loading-spinner {
  height: 200px; /* 给加载动画一个高度 */
  display: flex;
  justify-content: center;
  align-items: center;
}
.experiment-name-link {
  color: #409EFF;
  text-decoration: none;
}
.experiment-name-link:hover {
  text-decoration: underline;
}
.el-table .el-tag {
  /* 可以调整标签大小或边距 */
}
</style>
