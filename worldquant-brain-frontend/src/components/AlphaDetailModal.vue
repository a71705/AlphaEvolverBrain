// src/components/AlphaDetailModal.vue
<template>
  <el-dialog
    :model-value="visible"
    title="Alpha 详细信息"
    width="75%"
    :before-close="handleBeforeClose"
    top="5vh"
    destroy-on-close
    append-to-body
    class="alpha-detail-dialog"
  >
    <div v-if="loading" v-loading="loading" element-loading-text="正在加载Alpha详细数据..." class="modal-loading-spinner"></div>
    <div v-if="!loading && alphaDetail" class="alpha-detail-content">
      <el-descriptions title="基本信息" :column="2" border size="small">
        <el-descriptions-item label="Alpha ID (UUID)">{{ alphaDetail.id }}</el-descriptions-item>
        <el-descriptions-item label="实验 ID">{{ alphaDetail.experiment_id || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="表达式" :span="2">
          <pre class="expression-box">{{ alphaDetail.expression }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="描述">{{ alphaDetail.description || '无' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(alphaDetail.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="适应度得分">{{ formatNumber(alphaDetail.fitness_score, 4) }}</el-descriptions-item>
        <el-descriptions-item label="上次模拟时间">{{ formatDateTime(alphaDetail.simulated_at) }}</el-descriptions-item>
        <el-descriptions-item label="模拟状态">
            <el-tag :type="getSimulationStatusTag(alphaDetail.simulation_status)">
                {{ alphaDetail.simulation_status || '未知' }}
            </el-tag>
        </el-descriptions-item>
         <el-descriptions-item label="WQB模拟ID">{{ alphaDetail.wqb_simulation_id || 'N/A' }}</el-descriptions-item>
      </el-descriptions>

      <el-tabs v-model="activeTab" style="margin-top: 20px;">
        <el-tab-pane label="样本内统计 (IS Stats)" name="is_stats">
          <pre class="stats-box" v-if="alphaDetail.is_stats_json">{{ JSON.stringify(alphaDetail.is_stats_json, null, 2) }}</pre>
          <el-empty v-else description="无样本内统计数据"></el-empty>
        </el-tab-pane>
        <el-tab-pane label="样本内测试 (IS Tests)" name="is_tests">
          <pre class="stats-box" v-if="alphaDetail.is_tests_json">{{ JSON.stringify(alphaDetail.is_tests_json, null, 2) }}</pre>
          <el-empty v-else description="无样本内测试数据"></el-empty>
        </el-tab-pane>
        <el-tab-pane label="样本外统计 (OOS Stats)" name="oos_stats">
          <pre class="stats-box" v-if="alphaDetail.oos_stats_json">{{ JSON.stringify(alphaDetail.oos_stats_json, null, 2) }}</pre>
          <el-empty v-else description="无样本外统计数据"></el-empty>
        </el-tab-pane>
         <el-tab-pane label="样本外测试 (OOS Tests)" name="oos_tests">
          <pre class="stats-box" v-if="alphaDetail.oos_tests_json">{{ JSON.stringify(alphaDetail.oos_tests_json, null, 2) }}</pre>
          <el-empty v-else description="无样本外测试数据"></el-empty>
        </el-tab-pane>
        <el-tab-pane label="PnL 数据" name="pnl_data">
          <pre class="stats-box" v-if="alphaDetail.pnl_data_json">{{ JSON.stringify(alphaDetail.pnl_data_json, null, 2) }}</pre>
          <el-empty v-else description="无PnL数据"></el-empty>
        </el-tab-pane>
        <el-tab-pane label="年度统计" name="yearly_stats">
          <pre class="stats-box" v-if="alphaDetail.yearly_stats_data_json">{{ JSON.stringify(alphaDetail.yearly_stats_data_json, null, 2) }}</pre>
          <el-empty v-else description="无年度统计数据"></el-empty>
        </el-tab-pane>
        <el-tab-pane label="模拟配置" name="sim_config">
          <pre class="stats-box" v-if="alphaDetail.simulation_settings_json">{{ JSON.stringify(alphaDetail.simulation_settings_json, null, 2) }}</pre>
          <el-empty v-else description="无模拟配置信息"></el-empty>
        </el-tab-pane>
        <!-- DEV-048: 新增表达式结构标签页 -->
        <el-tab-pane label="表达式结构" name="tree_structure">
          <AlphaStructureViewer
            v-if="alphaDetail && alphaDetail.tree_structure_json"
            :tree-data="alphaDetail.tree_structure_json"
          />
          <el-empty v-else description="无表达式结构数据或后端未提供"></el-empty>
        </el-tab-pane>
      </el-tabs>

      <el-alert v-if="alphaDetail.simulation_error_message" :title="`模拟错误信息`" type="error" show-icon style="margin-top: 20px;">
        <pre style="white-space: pre-wrap; word-break: break-all;">{{alphaDetail.simulation_error_message}}</pre>
      </el-alert>

    </div>
    <div v-if="!loading && error && !alphaDetail" class="modal-error"> <!-- Show error only if no alphaDetail is loaded -->
      <el-empty :description="`加载Alpha详情失败: ${error}`"></el-empty>
    </div>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleForceClose">关闭</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script>
import { ref, watch, nextTick } from 'vue';
import axios from 'axios';
import { ElMessage, ElDialog, ElDescriptions, ElDescriptionsItem, ElTabs, ElTabPane, ElEmpty, ElAlert, ElButton, ElTag } from 'element-plus';
import AlphaStructureViewer from './AlphaStructureViewer.vue'; // DEV-048: 导入新组件

export default {
  name: 'AlphaDetailModal',
  components: { AlphaStructureViewer, ElDialog, ElDescriptions, ElDescriptionsItem, ElTabs, ElTabPane, ElEmpty, ElAlert, ElButton, ElTag }, // DEV-048: 注册组件
  props: {
    alphaId: {
      type: String, // Expecting UUID as string
      required: false, // Not required initially, will be set when modal opens
      default: null,
    },
    visible: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['close'],
  setup(props, { emit }) {
    const alphaDetail = ref(null);
    const loading = ref(false);
    const error = ref('');
    const activeTab = ref('is_stats');

    const fetchAlphaFullDetail = async (id) => {
      if (!id) {
        error.value = "Alpha ID 未提供。";
        alphaDetail.value = null;
        loading.value = false;
        return;
      }
      loading.value = true;
      error.value = '';
      alphaDetail.value = null; // Reset previous detail

      try {
        const apiUrl = process.env.VUE_APP_API_BASE_URL
                       ? `${process.env.VUE_APP_API_BASE_URL}/api/v1/alphas/${id}`
                       : `/api/v1/alphas/${id}`;
        const response = await axios.get(apiUrl, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
        });
        alphaDetail.value = response.data;
      } catch (err) {
        console.error(`获取Alpha ${id} 完整详情失败:`, err);
        if (err.response && err.response.status === 401) {
            error.value = '认证失败，请重新登录。';
        } else {
            error.value = `获取Alpha详情失败: ${err.response?.data?.detail || err.message}`;
        }
        ElMessage.error(error.value);
        alphaDetail.value = null;
      } finally {
        loading.value = false;
      }
    };

    const formatDateTime = (dateTimeString) => {
      if (!dateTimeString) return 'N/A';
      return new Date(dateTimeString).toLocaleString('zh-CN', { hour12: false });
    };

    const formatNumber = (num, precision = 2) => {
        if (num === null || num === undefined || num === '' || isNaN(parseFloat(num))) return 'N/A';
        return parseFloat(num).toFixed(precision);
    };

    const getSimulationStatusTag = (status) => {
        if (!status) return 'info';
        if (status.toUpperCase() === 'COMPLETED') return 'success';
        if (status.toUpperCase() === 'FAILED') return 'danger';
        if (status.toUpperCase() === 'RUNNING') return ''; // Default/Primary
        if (status.toUpperCase() === 'PENDING') return 'warning';
        return 'info';
    };

    watch(() => props.visible, (newVal) => {
      if (newVal && props.alphaId) {
        fetchAlphaFullDetail(props.alphaId);
      } else if (!newVal) {
        // Reset state when modal closes
        alphaDetail.value = null;
        activeTab.value = 'is_stats'; // DEV-048: 修正 activeTab 引用
        error.value = '';
        loading.value = false;
      }
    });

    // Watch for alphaId changes directly if the modal might stay open but content changes
    watch(() => props.alphaId, (newId, oldId) => {
        if (props.visible && newId && newId !== oldId) {
            fetchAlphaFullDetail(newId);
        } else if (props.visible && !newId) { // If modal is visible but ID becomes null
            alphaDetail.value = null;
            error.value = "Alpha ID 未提供。";
        }
    });


    const handleBeforeClose = (done) => {
      // This is called when user clicks outside or presses ESC
      // We want to ensure our custom close logic (emitting 'close') is called
      emit('close');
      done(); // Allow dialog to close
    };

    const handleForceClose = () => { // For the button
        emit('close');
    };


    return {
      alphaDetail,
      loading,
      error,
      activeTab,
      handleBeforeClose,
      handleForceClose,
      formatDateTime,
      formatNumber,
      getSimulationStatusTag,
    };
  }
};
</script>

<style scoped>
.modal-loading-spinner {
  height: 200px;
  display: flex;
  justify-content: center;
  align-items: center;
}
.alpha-detail-content pre, .expression-box {
  background-color: #f8f9fa; /* Lighter than f4f4f5 for better contrast with dialog */
  border: 1px solid #e9ecef; /* Lighter border */
  padding: 10px 15px; /* More padding */
  border-radius: 4px;
  font-size: 0.85em; /* Slightly smaller for more content */
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
  max-height: 250px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
.expression-box {
    max-height: 100px; /* Shorter for expression preview */
}
.stats-box {
    max-height: 300px; /* Allow more height for stats JSON */
}

/* Ensure dialog body is scrollable if content overflows viewport height */
.alpha-detail-dialog .el-dialog__body {
  max-height: calc(90vh - 120px); /* 90% of viewport height minus header/footer approx */
  overflow-y: auto;
  padding: 10px 20px; /* Adjust padding */
}
.el-descriptions {
    font-size: 13px; /* Slightly smaller desc items */
}
.el-descriptions__label {
    font-weight: bold;
}
.el-tabs__item {
    font-size: 14px;
}
</style>
