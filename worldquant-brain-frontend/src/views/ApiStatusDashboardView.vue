// src/views/ApiStatusDashboardView.vue
<template>
  <div class="api-status-dashboard-container">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>WorldQuant Brain API 使用状态与成本追踪</span>
          <el-button type="primary" :icon="RefreshRight" @click="fetchApiUsageData" :loading="loading" circle title="刷新数据"></el-button>
        </div>
      </template>

      <div v-if="loading && !apiUsageData" v-loading="loading" element-loading-text="正在加载API使用数据..." class="loading-placeholder"></div>

      <div v-if="apiUsageData">
        <el-alert
          v-if="apiUsageData.data_source && apiUsageData.data_source.includes('模拟数据')"
          title="提示：当前显示的是模拟API用量数据，非实时生产数据。"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom: 20px;"
        ></el-alert>

        <el-row :gutter="20">
          <el-col :xs="24" :sm="12" :md="8" :lg="6">
            <el-card shadow="hover" class="statistic-card">
              <el-statistic title="今日API调用次数 (应用记录)" :value="apiUsageData.total_calls_today || 0"></el-statistic>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6">
            <el-card shadow="hover" class="statistic-card">
              <el-statistic title="预估每日剩余配额" :value="apiUsageData.remaining_daily_quota !== null ? apiUsageData.remaining_daily_quota : 'N/A'"></el-statistic>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6">
            <el-card shadow="hover" class="statistic-card">
              <el-statistic title="预估每日总配额" :value="apiUsageData.total_daily_quota !== null ? apiUsageData.total_daily_quota : 'N/A'"></el-statistic>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6">
            <el-card shadow="hover" class="statistic-card">
              <el-statistic title="配额重置时间 (UTC)" :value="formatDateTime(apiUsageData.quota_reset_time) || 'N/A'"></el-statistic>
            </el-card>
          </el-col>
          <!--
          <el-col :xs="24" :sm="12" :md="8" :lg="6">
            <el-statistic title="今日预估API成本" :value="apiUsageData.estimated_cost_today !== null ? `¥${apiUsageData.estimated_cost_today.toFixed(2)}` : 'N/A'"></el-statistic>
          </el-col>
          -->
        </el-row>
        <p class="data-source-footer">数据来源: {{ apiUsageData.data_source || '未知' }}</p>
        <p class="data-source-footer">上次更新时间: {{ formatDateTime(lastUpdated) || 'N/A' }}</p>
      </div>

      <el-empty v-if="!loading && !apiUsageData && error" :description="`加载API使用数据失败: ${error}`"></el-empty>
      <el-empty v-if="!loading && !apiUsageData && !error && !initialLoadAttempted" description="正在准备加载数据..."></el-empty>
      <el-empty v-if="!loading && !apiUsageData && !error && initialLoadAttempted" description="暂无API使用数据"></el-empty>

    </el-card>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue';
import axios from 'axios';
import { ElMessage, ElStatistic, ElCard, ElRow, ElCol, ElEmpty, ElAlert, ElButton } from 'element-plus';
import { RefreshRight } from '@element-plus/icons-vue'; // Icon for refresh button

export default {
  name: 'ApiStatusDashboardView',
  components: { ElStatistic, ElCard, ElRow, ElCol, ElEmpty, ElAlert, ElButton },
  setup() {
    const apiUsageData = ref(null);
    const loading = ref(false);
    const error = ref('');
    const lastUpdated = ref(null);
    const initialLoadAttempted = ref(false); // Track if the first load attempt has been made
    let pollingInterval = null;

    const API_BASE_URL = process.env.VUE_APP_API_BASE_URL || '';

    const fetchApiUsageData = async (isManualRefresh = false) => {
      // Show loading only on initial load or manual refresh, not for background polling
      if (!apiUsageData.value || isManualRefresh) {
          loading.value = true;
      }
      error.value = ''; // Clear previous errors on new fetch attempt

      try {
        const apiUrl = `${API_BASE_URL}/api/v1/status/api_usage`;
        const response = await axios.get(apiUrl, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
        });
        apiUsageData.value = response.data;
        lastUpdated.value = new Date();
        if (!initialLoadAttempted.value) initialLoadAttempted.value = true;
      } catch (err) {
        console.error("获取API使用数据失败:", err);
        const errorMsg = `获取API使用数据失败: ${err.response?.data?.detail || err.message}`;
        if (!apiUsageData.value || isManualRefresh) {
            error.value = errorMsg; // Show error prominently if it's initial or manual refresh
            ElMessage.error(errorMsg);
        } else {
            console.warn(`轮询API使用数据失败: ${errorMsg}`); // Log silently for background polls
        }
        if (!initialLoadAttempted.value) initialLoadAttempted.value = true;
      } finally {
        loading.value = false;
      }
    };

    const formatDateTime = (dateTimeString) => {
      if (!dateTimeString) return null;
      try {
        const date = new Date(dateTimeString);
        if (isNaN(date.getTime())) return dateTimeString;
        return date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
      } catch(e) {
        return dateTimeString;
      }
    };

    onMounted(() => {
      fetchApiUsageData(true); // Initial load, show loading indicator
      pollingInterval = setInterval(() => {
        // console.debug("Polling API usage data..."); // Use console.debug for less noise
        fetchApiUsageData(false); // Background poll, don't show main loading unless data is null
      }, 60000); // 60秒
    });

    onUnmounted(() => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    });

    return {
      apiUsageData,
      loading,
      error,
      lastUpdated,
      initialLoadAttempted,
      fetchApiUsageData: () => fetchApiUsageData(true), // Manual refresh shows loading
      formatDateTime,
      RefreshRight, // Icon
    };
  }
};
</script>

<style scoped>
.api-status-dashboard-container {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 1.2em;
  font-weight: bold;
}
.loading-placeholder {
    min-height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.statistic-card {
  margin-bottom: 20px; /* Spacing between cards */
}
.el-statistic {
  text-align: center;
  padding: 15px; /* Increased padding */
}
.el-statistic :deep(.el-statistic__head) {
    font-size: 1rem; /* Adjusted from 1em */
    color: #606266;
    margin-bottom: 10px; /* Increased spacing */
}
.el-statistic :deep(.el-statistic__content) {
    font-size: 1.7rem; /* Adjusted from 1.8em */
    font-weight: 500; /* Slightly bolder */
}
.data-source-footer {
  font-size: 0.85em;
  color: #909399;
  margin-top: 15px;
  text-align: center;
}
</style>
