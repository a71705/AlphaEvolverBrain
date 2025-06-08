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

    <el-card class="box-card alpha-table-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>Alpha 表现</span>
        </div>
      </template>
      <AlphaTable v-if="experiment && experiment.id" :experiment-id="experiment.id" />
    </el-card>

    <el-card class="box-card fitness-chart-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>适应度演化曲线</span>
        </div>
      </template>
      <FitnessChart v-if="experiment" :fitness-data="formattedFitnessHistory" :loading="chartLoadingInitial" />
      <div v-else-if="loading && !experiment" class="chart-initial-loading" style="text-align: center; padding: 20px; color: #909399;">图表数据随实验详情加载中...</div>
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
import AlphaTable from '@/components/AlphaTable.vue';
import FitnessChart from '@/components/FitnessChart.vue'; // 导入 FitnessChart

export default {
  name: 'ExperimentDetailView',
  components: { AlphaTable, FitnessChart, ElStatistic, ElProgress, ElDescriptions, ElDescriptionsItem, ElTag, ElCard, ElRow, ElCol, ElEmpty },
  setup() {
    const route = useRoute();
    const experimentId = ref(route.params.experimentId);
    const experiment = ref(null);
    const loading = ref(false); // Main experiment data loading
    const error = ref('');
    const chartLoadingInitial = ref(true); // Separate loading state for chart, initially true until first data load

    let pollingInterval = null;

    const fetchExperimentDetail = async () => {
      if (!experimentId.value) {
        error.value = "实验ID未提供";
        loading.value = false;
        chartLoadingInitial.value = false;
        return;
      }

      if (!experiment.value && !pollingInterval) {
          loading.value = true;
          chartLoadingInitial.value = true; // Also true during initial full load
      }
      error.value = '';

      try {
        const apiUrl = process.env.VUE_APP_API_BASE_URL
                       ? `${process.env.VUE_APP_API_BASE_URL}/api/v1/experiments/${experimentId.value}`
                       : `/api/v1/experiments/${experimentId.value}`;
        const response = await axios.get(apiUrl, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
        });
        experiment.value = response.data;
        chartLoadingInitial.value = false; // Data loaded, chart can now process
      } catch (err) {
        console.error(`获取实验 ${experimentId.value} 详情失败:`, err);
        let errorMsg = '';
        if (err.response && err.response.status === 401) {
            errorMsg = '认证失败，请重新登录。';
        } else if (err.response && err.response.data && err.response.data.detail) {
          errorMsg = err.response.data.detail;
        } else if (err.request) {
          errorMsg = '无法连接到服务器。';
        } else {
          errorMsg = err.message;
        }

        if (!pollingInterval && !experiment.value) {
            error.value = errorMsg;
            ElMessage.error(`加载实验数据失败: ${errorMsg}`);
        } else {
            console.warn(`轮询实验 ${experimentId.value} 数据失败: ${errorMsg}`);
        }
        chartLoadingInitial.value = false; // Error occurred, stop chart loading
      } finally {
        if (loading.value && !pollingInterval) loading.value = false;
      }
    };

    const formattedFitnessHistory = computed(() => {
      // Attempt to get fitness_history from ga_config_json first
      if (experiment.value?.ga_config_json?.fitness_history && Array.isArray(experiment.value.ga_config_json.fitness_history)) {
        return experiment.value.ga_config_json.fitness_history.map(item => ({
          iteration: item.iteration ?? item.generation, // Prefer iteration, fallback to generation
          fitness: item.best_fitness ?? item.fitness,    // Prefer best_fitness, fallback to fitness
          avg_fitness: item.avg_fitness
        })).sort((a, b) => (a.iteration || 0) - (b.iteration || 0)); // Ensure sorted by iteration
      }
      // Fallback: if experiment.value.alphas (full alpha list) is available and fitness_history is not.
      // This is less ideal as it might be a very large list and not directly represent generation-wise progress.
      // This part is more of a placeholder if direct fitness_history is missing.
      if (experiment.value?.alphas && Array.isArray(experiment.value.alphas)) {
        console.warn("FitnessChart: 'ga_config_json.fitness_history' not found or invalid, attempting to use 'alphas' array. This may not be optimal for performance chart.");
        // This assumes alphas have 'iteration' and 'fitness_score' and are somewhat representative
        return experiment.value.alphas
          .filter(alpha => alpha.ga_metadata_json?.iteration !== undefined && alpha.fitness_score !== undefined)
          .map(alpha => ({
            iteration: alpha.ga_metadata_json.iteration,
            fitness: alpha.fitness_score
          }))
          .sort((a,b) => a.iteration - b.iteration);
      }
      return []; // Default to empty if no suitable data found
    });

    const progressPercentage = computed(() => {
      if (experiment.value && experiment.value.current_progress !== undefined && experiment.value.current_progress !== null) {
        return Math.max(0, Math.min(100, Number(experiment.value.current_progress)));
      }
      if (experiment.value?.status === 'COMPLETED') return 100;
      if (experiment.value?.status === 'FAILED' || experiment.value?.status === 'CANCELLED') return experiment.value.current_progress || 0;
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
      formattedFitnessHistory,
      chartLoadingInitial, // Use this for the chart's loading prop
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
/* Removed #alpha-performance-table-placeholder and #fitness-evolution-chart-placeholder specific styles */
/* as components will define their own structure */
.chart-initial-loading { /* For the text shown before chart component has data */
    min-height: 100px;
    padding: 20px;
    text-align: center;
    color: #909399;
}
</style>
