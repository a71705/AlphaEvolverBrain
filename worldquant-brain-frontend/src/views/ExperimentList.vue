<template>
  <div class="experiment-list-container">
    <!-- 页面标题 -->
    <h2 class="page-title">实验列表</h2>

    <!-- 操作按钮区域，例如新建实验按钮 -->
    <div class="actions-bar">
      <el-button type="primary" @click="navigateToCreateExperiment">
        <el-icon><Plus /></el-icon> 新建实验
      </el-button>
    </div>

    <!-- 加载状态提示 -->
    <div v-if="loading" class="loading-spinner">
      <el-icon class="is-loading" size="24px"><Loading /></el-icon>
      <span>正在加载实验数据...</span>
    </div>

    <!-- 错误提示 -->
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="true"
      @close="errorMessage = ''"
      class="error-alert"
    />

    <!-- 实验数据表格 -->
    <el-table
      v-if="!loading && !errorMessage && experiments.length > 0"
      :data="experiments"
      style="width: 100%"
      stripe
      border
      empty-text="暂无实验数据"
    >
      <!-- 实验名称列 -->
      <el-table-column prop="name" label="实验名称" min-width="180">
        <template #default="scope">
          <!-- 可以让名称也作为详情页链接 -->
          <router-link :to="getExperimentDetailLink(scope.row.id)" class="experiment-name-link">
            {{ scope.row.name }}
          </router-link>
        </template>
      </el-table-column>

      <!-- 状态列 -->
      <el-table-column prop="status" label="状态" width="120">
        <template #default="scope">
          <el-tag :type="getStatusTagType(scope.row.status)">
            {{ formatStatus(scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 开始时间列 -->
      <el-table-column prop="start_time" label="开始时间" width="180">
        <template #default="scope">
          {{ formatDateTime(scope.row.start_time) }}
        </template>
      </el-table-column>

      <!-- 当前进度列 (来自 DEV-017 的 progress_percentage) -->
      <el-table-column prop="progress_percentage" label="进度" width="150">
        <template #default="scope">
          <el-progress
            :percentage="scope.row.progress_percentage || 0"
            :status="getExperimentProgressStatus(scope.row.status, scope.row.progress_percentage)"
          />
        </template>
      </el-table-column>

      <!-- 操作列 -->
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="scope">
          <el-button
            size="small"
            type="primary"
            @click="navigateToExperimentDetail(scope.row.id)"
          >
            查看详情
          </el-button>
          <!-- 更多操作，如删除、停止等，可以在未来添加 -->
          <!--
          <el-button
            size="small"
            type="danger"
            @click="handleDeleteExperiment(scope.row.id)"
            style="margin-left: 5px;"
            v-if="canDelete(scope.row.status)"
          >
            删除
          </el-button>
          -->
        </template>
      </el-table-column>
    </el-table>

    <!-- 无数据提示 (当非加载且无错误，但数据为空时) -->
     <el-empty
        v-if="!loading && !errorMessage && experiments.length === 0"
        description="暂无实验数据，您可以尝试新建一个实验。"
      >
        <el-button type="primary" @click="navigateToCreateExperiment">立即新建</el-button>
      </el-empty>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { ElMessage, ElMessageBox, ElTag, ElProgress } from 'element-plus'; // 引入需要的 Element Plus 组件
import { Loading, Plus } from '@element-plus/icons-vue'; // 引入 Element Plus 图标

// 定义实验数据接口类型 (与 DEV-017 ExperimentResponse 对应)
interface Experiment {
  id: string;
  name: string;
  description?: string;
  status: string; // 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'
  start_time: string; // ISO 格式日期时间字符串
  end_time?: string;
  config_json: object;
  current_depth?: number;
  current_iteration?: number;
  progress_percentage?: number; // 来自后端计算
  // ... 其他字段根据需要添加
}

const router = useRouter(); // 获取路由实例
const experiments = ref<Experiment[]>([]); // 存储实验数据的响应式引用
const loading = ref(true); // 加载状态的响应式引用
const errorMessage = ref(''); // 错误信息的响应式引用

// 组件挂载后执行的数据获取逻辑
onMounted(async () => {
  await fetchExperiments();
});

// 获取实验数据的异步函数
const fetchExperiments = async () => {
  loading.value = true;
  errorMessage.value = '';
  try {
    // 从后端 API 获取实验数据
    // 假设 API 支持分页和过滤，但基础版本暂时不实现前端控制
    const response = await axios.get<Experiment[]>('/api/v1/experiments?limit=100&offset=0'); // 获取较多数据以便测试
    experiments.value = response.data;
  } catch (error: any) {
    console.error('获取实验列表失败:', error);
    if (axios.isAxiosError(error) && error.response) {
      errorMessage.value = `获取实验数据失败: ${error.response.data.detail || error.message}`;
    } else {
      errorMessage.value = '获取实验数据失败，请检查网络或联系管理员。';
    }
    experiments.value = []; // 清空数据以防显示旧数据
  } finally {
    loading.value = false; // 结束加载状态
  }
};

// 格式化日期时间 (例如：YYYY-MM-DD HH:mm:ss)
const formatDateTime = (dateTimeString?: string): string => {
  if (!dateTimeString) return 'N/A';
  try {
    const date = new Date(dateTimeString);
    return date.toLocaleString('zh-CN', { hour12: false });
  } catch (e) {
    return dateTimeString; // 如果转换失败，返回原始字符串
  }
};

// 格式化实验状态显示文本
const formatStatus = (status: string): string => {
  const statusMap: { [key: string]: string } = {
    PENDING: '待处理',
    RUNNING: '运行中',
    COMPLETED: '已完成',
    FAILED: '失败',
    CANCELLED: '已取消',
  };
  return statusMap[status] || status;
};

// 根据实验状态返回 Element Plus Tag 的类型
const getStatusTagType = (status: string): ('success' | 'info' | 'warning' | 'danger' | undefined) => { // Changed '' to undefined
  switch (status) {
    case 'COMPLETED':
      return 'success';
    case 'RUNNING':
      return 'info';
    case 'PENDING':
      return 'warning';
    case 'FAILED':
    case 'CANCELLED':
      return 'danger';
    default:
      return undefined; // Return undefined for default tag type
  }
};

// 根据实验状态和进度返回 Element Plus Progress 的状态
const getExperimentProgressStatus = (status: string, percentage?: number): ('success' | 'exception' | 'warning' | undefined) => {
  if (status === 'COMPLETED') return 'success';
  if (status === 'FAILED' || status === 'CANCELLED') return 'exception';
  if (status === 'RUNNING' && (percentage !== undefined && percentage < 100) ) return undefined; // 默认颜色
  if (status === 'PENDING') return 'warning';
  return undefined;
};


// 导航到实验详情页
const navigateToExperimentDetail = (experimentId: string) => {
  router.push({ name: 'experiment-detail', params: { experimentId } }); // 假设详情页路由名为 'experiment-detail'
};
// 获取实验详情页链接 (用于 router-link)
const getExperimentDetailLink = (experimentId: string) => {
  // 确保路由配置中有一个名为 'experiment-detail' 且接收 experimentId 参数的路由
  // 例如: path: '/experiments/:experimentId', name: 'experiment-detail', ...
  // 这个路由将在 DEV-029 中正式创建。目前先定义，确保链接能生成。
  return { name: 'experiment-detail', params: { experimentId } };
};


// 导航到新建实验页面 (占位)
const navigateToCreateExperiment = () => {
  ElMessage.info('新建实验功能正在开发中...');
  // router.push({ name: 'create-experiment' }); // 假设有此路由
};

// 处理删除实验 (占位)
// const handleDeleteExperiment = async (experimentId: string) => {
//   try {
//     await ElMessageBox.confirm(
//       '确定要删除这个实验吗？此操作不可恢复。',
//       '警告',
//       {
//         confirmButtonText: '确定删除',
//         cancelButtonText: '取消',
//         type: 'warning',
//       }
//     );
//     // 调用 API 删除实验
//     // await axios.delete(`/api/v1/experiments/${experimentId}`);
//     ElMessage.success('实验已删除（模拟）。');
//     // fetchExperiments(); // 重新加载列表
//   } catch (error) {
//     // 用户取消或API调用失败
//     if (error !== 'cancel') {
//       ElMessage.error('删除实验失败（模拟）。');
//     }
//   }
// };

// const canDelete = (status: string): boolean => {
//   return !['RUNNING'].includes(status); // 例如，运行中的实验不能删除
// };

</script>

<style scoped>
.experiment-list-container {
  padding: 20px;
}

.page-title {
  margin-bottom: 20px;
  font-size: 24px;
  font-weight: bold;
}

.actions-bar {
  margin-bottom: 20px;
  text-align: right; /* 按钮靠右 */
}

.loading-spinner {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px;
  font-size: 16px;
  color: #555;
}
.loading-spinner .el-icon {
  margin-right: 8px;
}

.error-alert {
  margin-bottom: 20px;
}

.experiment-name-link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.experiment-name-link:hover {
  text-decoration: underline;
}
</style>
