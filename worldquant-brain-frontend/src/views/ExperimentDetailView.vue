// src/views/ExperimentDetailView.vue
<template>
  <div class="experiment-detail-container" v-if="experiment">
    <el-card class="box-card experiment-info-card">
      <template #header>
        <div class="card-header">
          <span>实验详情: {{ experiment.name }}</span>
          <el-tag :type="getStatusTagType(experiment.status)" style="margin-left: 10px;">{{ experiment.status }}</el-tag>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="实验ID">{{ experiment.id }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatDateTime(experiment.created_at) }}</el-descriptions-item> <!-- Assuming start_time is created_at -->
        <el-descriptions-item label="结束时间">{{ formatDateTime(experiment.updated_at) }}</el-descriptions-item> <!-- Assuming end_time is updated_at for completed/failed -->
        <el-descriptions-item label="代码版本">{{ experiment.code_version || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ experiment.description || '无' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="box-card experiment-progress-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>实验进度</span>
        </div>
      </template>
      <div v-if="experiment.status === 'RUNNING' || experiment.status === 'PENDING'">
        <el-progress
          :text-inside="true"
          :stroke-width="24"
          :percentage="progressPercentage"
          :status="getProgressStatus(experiment.status, progressPercentage)"
          style="margin-bottom: 10px;"
        />
        <el-row :gutter="20">
          <el-col :span="8">
            <el-statistic title="当前阶段/深度" :value="experiment.current_depth || 0"></el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic title="当前迭代" :value="experiment.current_iteration_at_depth || 0"></el-statistic> <!-- Mapped to current_iteration_at_depth -->
          </el-col>
          <el-col :span="8">
             <el-statistic title="随机种子" :value="experiment.ga_config_json?.random_seed || 'N/A'"></el-statistic> <!-- Assuming random_seed in ga_config_json -->
          </el-col>
        </el-row>
      </div>
      <div v-else>
        <p>实验已 {{ experiment.status === 'COMPLETED' ? '完成' : (experiment.status === 'FAILED' ? '失败' : '结束 (' + experiment.status + ')') }}。</p>
        <el-progress
          :text-inside="true"
          :stroke-width="24"
          :percentage="progressPercentage"
          :status="getProgressStatus(experiment.status, progressPercentage)"
        />
      </div>
    </el-card>

    <!-- 为 DEV-030 (Alpha性能表格) 预留区域 -->
    <el-card class="box-card alpha-table-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>Alpha 表现</span>
        </div>
      </template>
      <!-- AlphaTable 组件将在此处渲染 (DEV-030) -->
      <AlphaTable v-if="experiment && experiment.id" :experiment-id="experiment.id" />
    </el-card>

    <!-- 为 DEV-031 (适应度曲线图表) 预留区域 -->
    <el-card class="box-card fitness-chart-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>适应度演化曲线</span>
        </div>
      </template>
      <div id="fitness-evolution-chart-placeholder">
        <p style="text-align: center; color: #909399;">适应度演化图表加载区域 (DEV-031)</p>
      </div>
    </el-card>

  </div>
  <div v-else-if="loading" v-loading="loading" element-loading-text="正在加载实验详情..." class="loading-placeholder"></div>
  <el-empty v-else-if="error" :description="`加载实验失败: ${error}`"></el-empty>
</template>

<script>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import axios from 'axios';
import { ElMessage, ElStatistic, ElProgress, ElDescriptions, ElDescriptionsItem, ElTag, ElCard, ElRow, ElCol, ElEmpty } from 'element-plus';
        import AlphaTable from '@/components/AlphaTable.vue'; // 导入 AlphaTable

export default {
  name: 'ExperimentDetailView',
          components: { AlphaTable, ElStatistic, ElProgress, ElDescriptions, ElDescriptionsItem, ElTag, ElCard, ElRow, ElCol, ElEmpty },
  setup() {
    const route = useRoute();
            const experimentId = ref(route.params.experimentId);
    const experiment = ref(null);
    const loading = ref(false);
    const error = ref('');
    let pollingInterval = null;

    const fetchExperimentDetail = async () => {
      if (!experimentId.value) {
        error.value = "实验ID未提供";
        loading.value = false;
        return;
      }
      // 首次加载或非轮询时显示全局加载状态
      if (!experiment.value && !pollingInterval) loading.value = true; // Only show global loading on initial load
      error.value = '';

      try {
        const apiUrl = process.env.VUE_APP_API_BASE_URL
                       ? `${process.env.VUE_APP_API_BASE_URL}/api/v1/experiments/${experimentId.value}`
                       : `/api/v1/experiments/${experimentId.value}`;
        const response = await axios.get(apiUrl, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` } // 添加认证头
        });
        experiment.value = response.data;
      } catch (err) {
        console.error(`获取实验 ${experimentId.value} 详情失败:`, err);
        if (err.response && err.response.status === 401) {
            error.value = '认证失败，请重新登录。';
            // router.push('/login'); // 可选：如果认证失败则跳转到登录页
        } else if (err.response && err.response.data && err.response.data.detail) {
          error.value = err.response.data.detail;
        } else if (err.request) {
          error.value = '无法连接到服务器。';
        } else {
          error.value = err.message;
        }
        if (!pollingInterval && !experiment.value) { // 只有在首次加载失败时才显示全局错误提示
            ElMessage.error(`加载实验数据失败: ${error.value}`);
        } else {
            console.warn(`轮询实验 ${experimentId.value} 数据失败: ${error.value}`);
        }
      } finally {
        if (loading.value && !pollingInterval) loading.value = false;
      }
    };

    const progressPercentage = computed(() => {
      if (experiment.value && experiment.value.current_progress !== undefined && experiment.value.current_progress !== null) {
        return Math.max(0, Math.min(100, Number(experiment.value.current_progress)));
      }
      if (experiment.value?.status === 'COMPLETED') return 100;
      if (experiment.value?.status === 'FAILED' || experiment.value?.status === 'CANCELLED') return experiment.value.current_progress || 0; // 保留失败时的进度
      return 0;
    });

    const getProgressStatus = (status, percentage) => {
      if (status === 'FAILED') return 'exception';
      if (status === 'COMPLETED' || percentage === 100) return 'success';
      if (status === 'RUNNING' || status === 'PENDING') return undefined;
      return 'warning';
    };

    const getStatusTagType = (status) => {
      switch (status) {
        case 'PENDING': return 'info';
        case 'RUNNING': return '';
        case 'COMPLETED': return 'success';
        case 'FAILED': return 'danger';
        case 'CANCELLED': return 'warning';
        default: return 'info';
      }
    };

    const formatDateTime = (dateTimeString) => {
      if (!dateTimeString) return null;
      const date = new Date(dateTimeString);
      return date.toLocaleString('zh-CN', { hour12: false });
    };

    onMounted(() => {
      fetchExperimentDetail();
      pollingInterval = setInterval(() => {
        if (experiment.value && (experiment.value.status === 'RUNNING' || experiment.value.status === 'PENDING')) {
          fetchExperimentDetail();
        } else if (pollingInterval) {
          clearInterval(pollingInterval);
          pollingInterval = null;
        }
      }, 10000);
    });

    onUnmounted(() => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    });

    return {
      experiment,
      loading,
      error,
      progressPercentage,
      getStatusTagType,
      getProgressStatus,
      formatDateTime,
              // experimentId, // experiment.id is used in template, experimentId is for key or direct prop if needed
    };
  }
};
</script>

<style scoped>
.experiment-detail-container {
  padding: 20px;
}
.box-card {
  /* 卡片统一样式 */
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1.2em;
  font-weight: bold;
}
.loading-placeholder {
    height: 300px; /* 给加载动画一个高度 */
    display: flex;
    justify-content: center;
    align-items: center;
}
.el-descriptions {
  margin-top: 10px;
}
.el-statistic {
  text-align: center;
}
#alpha-performance-table-placeholder,
#fitness-evolution-chart-placeholder {
    min-height: 100px; /* 占位符最小高度 */
    padding: 20px;
    border: 1px dashed #dcdfe6;
    border-radius: 4px;
    margin-top: 10px;
}
</style>
