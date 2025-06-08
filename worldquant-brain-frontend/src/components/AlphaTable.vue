// src/components/AlphaTable.vue
<template>
  <div class="alpha-table-container">
    <div v-if="loading" v-loading="loading" class="loading-spinner" element-loading-text="正在加载 Alpha 数据..."></div>
    <el-table
      v-if="!loading && alphas.length > 0"
      :data="alphas"
      style="width: 100%"
      border
      empty-text="此实验暂无 Alpha 数据"
      @sort-change="handleSortChange"
      :default-sort="defaultSort"
    >
      <el-table-column prop="id" label="Alpha ID" sortable="custom" width="120" :show-overflow-tooltip="true">
         <template #default="scope">
            <el-link type="primary" @click="openAlphaDetailModal(scope.row)">{{ scope.row.id.substring(0, 8) }}...</el-link>
         </template>
      </el-table-column>
      <el-table-column prop="expression" label="表达式" :show-overflow-tooltip="true" min-width="200"></el-table-column>
      <el-table-column prop="fitness_score" label="适应度得分" sortable="custom" width="150" align="right"> <!-- API 返回的是 fitness_score -->
        <template #default="scope">{{ formatNumber(scope.row.fitness_score, 4) }}</template>
      </el-table-column>
      <el-table-column prop="is_stats_json.sharpe" label="Sharpe (IS)" sortable="custom" width="150" align="right">
        <template #default="scope">{{ formatNumber(scope.row.is_stats_json?.sharpe, 3) }}</template>
      </el-table-column>
      <el-table-column prop="is_stats_json.returns" label="Returns (IS)" sortable="custom" width="150" align="right">
        <template #default="scope">{{ formatNumber(scope.row.is_stats_json?.returns, 3) }}</template>
      </el-table-column>
       <el-table-column prop="depth" label="深度" sortable="custom" width="100" align="center">
         <template #default="scope">{{ scope.row.ga_metadata_json?.depth !== undefined ? scope.row.ga_metadata_json.depth : 'N/A' }}</template>
       </el-table-column>
      <el-table-column prop="iteration" label="迭代" sortable="custom" width="100" align="center">
        <template #default="scope">{{ scope.row.ga_metadata_json?.iteration !== undefined ? scope.row.ga_metadata_json.iteration : 'N/A' }}</template>
      </el-table-column>
      <el-table-column prop="simulated_at" label="模拟时间" sortable="custom" width="180">
        <template #default="scope">{{ formatDateTime(scope.row.simulated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right" align="center">
        <template #default="scope">
          <el-button size="small" type="primary" @click="openAlphaDetailModal(scope.row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && alphas.length === 0" description="此实验没有生成 Alpha 或不符合当前筛选条件"></el-empty>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" style="margin-top: 15px;"></el-alert>

    <!-- Alpha 详情模态框 -->
    <AlphaDetailModal v-if="selectedAlpha" :alpha-id="selectedAlpha.id" :visible="detailModalVisible" @close="closeAlphaDetailModal" />
  </div>
</template>

<script>
import { ref, watch, onMounted } from 'vue';
import axios from 'axios';
import AlphaDetailModal from './AlphaDetailModal.vue'; // 引入详情模态框组件
import { ElMessage, ElLoading } from 'element-plus'; // Import ElLoading for potential full-screen loading

export default {
  name: 'AlphaTable',
  components: { AlphaDetailModal },
  props: {
    experimentId: {
      type: String,
      required: true,
    },
    // 可以添加其他过滤参数作为 props
  },
  setup(props) {
    const alphas = ref([]);
    const loading = ref(false);
    const error = ref('');
    const selectedAlpha = ref(null); // Will store the full alpha object for the modal
    const detailModalVisible = ref(false);

    // 排序状态 - API 使用 fitness_score
    const defaultSort = ref({ prop: 'fitness_score', order: 'descending' });
    const sortParams = ref({ ...defaultSort.value });


    const fetchAlphas = async () => {
      if (!props.experimentId) {
        error.value = '实验ID未提供，无法加载Alphas。';
        alphas.value = [];
        return;
      }
      loading.value = true;
      error.value = '';
      try {
        const apiUrl = process.env.VUE_APP_API_BASE_URL
                       ? `${process.env.VUE_APP_API_BASE_URL}/api/v1/experiments/${props.experimentId}/alphas`
                       : `/api/v1/experiments/${props.experimentId}/alphas`;

        const params = {
          // limit: 100, // 示例：可以添加分页参数
          // offset: 0,
          sort_by: sortParams.value.prop,
          order: sortParams.value.order === 'ascending' ? 'asc' : 'desc',
        };

        const response = await axios.get(apiUrl, {
            params,
            headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
        });
        // 假设后端返回的是 AlphaResponse 列表，其中 ga_metadata_json 包含 depth 和 iteration
        alphas.value = response.data.alphas || response.data || []; // Adapt based on actual API response structure (e.g. if paginated)
      } catch (err) {
        console.error(`获取实验 ${props.experimentId} 的Alphas失败:`, err);
        if (err.response && err.response.status === 401) {
            error.value = '认证失败，请重新登录。';
        } else {
            error.value = `获取Alphas失败: ${err.response?.data?.detail || err.message}`;
        }
        ElMessage.error(error.value);
        alphas.value = [];
      } finally {
        loading.value = false;
      }
    };

    const handleSortChange = ({ prop, order }) => {
      sortParams.value.prop = prop;
      sortParams.value.order = order;
      fetchAlphas();
    };

    const formatDateTime = (dateTimeString) => {
      if (!dateTimeString) return 'N/A';
      return new Date(dateTimeString).toLocaleString('zh-CN', { hour12: false });
    };

    const formatNumber = (num, precision = 2) => {
        if (num === null || num === undefined || num === '' || isNaN(parseFloat(num))) return 'N/A';
        return parseFloat(num).toFixed(precision);
    };

    const openAlphaDetailModal = (alpha) => {
      selectedAlpha.value = alpha; // Store the alpha object
      detailModalVisible.value = true;
    };

    const closeAlphaDetailModal = () => {
      detailModalVisible.value = false;
      selectedAlpha.value = null;
    };

    watch(() => props.experimentId, (newId, oldId) => {
      if (newId && newId !== oldId) {
        sortParams.value = { ...defaultSort.value }; // Reset sort on experiment change
        fetchAlphas();
      }
    }, { immediate: true }); // Fetch on initial load as well

    // onMounted(fetchAlphas); // Replaced by immediate watch

    return {
      alphas,
      loading,
      error,
      selectedAlpha,
      detailModalVisible,
      defaultSort,
      fetchAlphas,
      handleSortChange,
      formatDateTime,
      formatNumber,
      openAlphaDetailModal,
      closeAlphaDetailModal,
    };
  }
};
</script>

<style scoped>
.alpha-table-container {
  margin-top: 0px;
}
.loading-spinner {
  height: 150px;
  display: flex;
  justify-content: center;
  align-items: center;
}
.el-link {
  font-size: 12px;
}
</style>
