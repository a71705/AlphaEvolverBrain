// src/views/AlphaComparisonView.vue
<template>
  <div class="alpha-comparison-container">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>高级 Alpha 性能比较</span>
        </div>
      </template>

      <!-- Alpha 选择区域 -->
      <div class="alpha-selection-area">
        <el-select
          v-model="selectedAlphaIds"
          multiple
          filterable
          remote
          reserve-keyword
          placeholder="搜索并选择要比较的 Alpha ID 或表达式片段"
          :remote-method="searchAlphas"
          :loading="alphaSearchLoading"
          loading-text="正在搜索Alphas..."
          no-data-text="未找到Alpha，尝试更宽泛的搜索词"
          no-match-text="无匹配Alpha"
          style="width: 100%; margin-bottom: 20px;"
          value-key="id"
          @change="handleSelectionChange"
          clearable
        >
          <el-option
            v-for="item in searchableAlphas"
            :key="item.id"
            :label="`${item.name} (ID: ${item.id.substring(0,8)}... Fitness: ${formatNumber(item.fitness, 3)})`"
            :value="item.id">
             <span style="float: left; max-width: 70%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ item.name }} (ID: {{ item.id.substring(0,8) }}...)</span>
             <span style.float="right" :style="{ color: getFitnessColor(item.fitness), fontSize: '13px', marginLeft: '10px' }">
                Fitness: {{ formatNumber(item.fitness, 3) }}
             </span>
          </el-option>
        </el-select>
      </div>

      <div v-if="loadingComparisonData" v-loading="loadingComparisonData" element-loading-text="正在加载比较数据..." class="charts-loading-spinner"></div>

      <el-tabs v-model="activeTab" v-if="!loadingComparisonData && selectedAlphasData.length > 0" type="border-card">
        <el-tab-pane label="PnL 曲线叠加" name="pnl">
          <div class="chart-wrapper" style="height: 450px;">
            <Line v-if="pnlChartData.datasets && pnlChartData.datasets.length" :data="pnlChartData" :options="pnlChartOptions" />
            <el-empty v-else description="无 PnL 数据或所选 Alpha 无有效 PnL 数据"></el-empty>
          </div>
        </el-tab-pane>
        <el-tab-pane label="关键指标对比 (IS)" name="is_metrics">
          <div class="chart-wrapper" style="height: 450px;">
            <Bar v-if="isMetricsChartData.datasets && isMetricsChartData.datasets.length" :data="isMetricsChartData" :options="metricsChartOptionsIS" />
            <el-empty v-else description="无样本内关键指标数据或未能生成图表"></el-empty>
          </div>
        </el-tab-pane>
        <el-tab-pane label="关键指标对比 (OOS)" name="oos_metrics">
          <div class="chart-wrapper" style="height: 450px;">
             <Bar v-if="oosMetricsChartData.datasets && oosMetricsChartData.datasets.length" :data="oosMetricsChartData" :options="metricsChartOptionsOOS" />
             <el-empty v-else description="无样本外关键指标数据或未能生成图表"></el-empty>
          </div>
        </el-tab-pane>
      </el-tabs>
      <el-empty v-if="!loadingComparisonData && selectedAlphasData.length === 0 && selectionAttempted"
                 description="请至少选择一个 Alpha 进行比较，或所选Alpha无有效数据。尝试不同的Alpha。">
      </el-empty>
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" style="margin-top: 15px;"></el-alert>

    </el-card>
  </div>
</template>

<script>
import { ref, reactive, computed, watch } from 'vue';
import axios from 'axios';
import { ElMessage, ElSelect, ElOption, ElTabs, ElTabPane, ElCard, ElEmpty, ElAlert } from 'element-plus';
import { Line, Bar } from 'vue-chartjs';
import { Chart as ChartJS, Title, Tooltip, Legend, LineElement, BarElement, CategoryScale, LinearScale, PointElement, Colors } from 'chart.js';

ChartJS.register(Title, Tooltip, Legend, LineElement, BarElement, CategoryScale, LinearScale, PointElement, Colors);
// ChartJS.defaults.color = '#FFF'; // Example for dark theme, ensure it's set globally or per chart options

// Helper for chart colors
const chartColors = ['rgb(75, 192, 192)', 'rgb(255, 99, 132)', 'rgb(54, 162, 235)', 'rgb(255, 205, 86)', 'rgb(153, 102, 255)', 'rgb(255, 159, 64)', 'rgb(199, 199, 199)'];
const chartBgColors = chartColors.map(color => color.replace('rgb', 'rgba').replace(')', ', 0.5)'));


export default {
  name: 'AlphaComparisonView',
  components: { Line, Bar, ElSelect, ElOption, ElTabs, ElTabPane, ElCard, ElEmpty, ElAlert },
  setup() {
    const selectedAlphaIds = ref([]);
    const searchableAlphas = ref([]);
    const alphaSearchLoading = ref(false);
    const selectedAlphasData = ref([]);
    const loadingComparisonData = ref(false);
    const error = ref('');
    const activeTab = ref('pnl');
    const selectionAttempted = ref(false);

    const API_BASE_URL = process.env.VUE_APP_API_BASE_URL || '';

    const searchAlphas = async (query) => {
      if (query && query.trim().length > 2) { // Only search if query is substantial
        alphaSearchLoading.value = true;
        try {
          const response = await axios.get(`${API_BASE_URL}/api/v1/alphas`, {
             params: { search: query, limit: 50, sort_by: 'fitness_score', order: 'desc' },
             headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
          });
          searchableAlphas.value = (response.data.alphas || response.data || []).map(alpha => ({ // Adapt to actual response structure
            id: alpha.id,
            name: alpha.expression.substring(0, 40) + (alpha.expression.length > 40 ? "..." : ""),
            fitness: alpha.fitness_score
          }));
        } catch (err) {
          console.error("搜索Alphas失败:", err);
          searchableAlphas.value = [];
          ElMessage.error(`搜索Alphas失败: ${err.response?.data?.detail || err.message}`);
        } finally {
          alphaSearchLoading.value = false;
        }
      } else {
        searchableAlphas.value = [];
      }
    };

    const formatNumber = (num, precision = 2) => {
        if (num === null || num === undefined || num === '' || isNaN(parseFloat(num))) return 'N/A';
        return parseFloat(num).toFixed(precision);
    };

    const getFitnessColor = (fitness) => {
        if (fitness === null || fitness === undefined) return '#909399'; // Grey for N/A
        if (fitness >= 1.5) return '#67C23A'; // Green for high fitness
        if (fitness >= 0.5) return '#E6A23C'; // Yellow for medium
        return '#F56C6C'; // Red for low
    };

    const handleSelectionChange = async (newSelectedIds) => {
      selectionAttempted.value = true;
      if (!newSelectedIds || newSelectedIds.length === 0) {
        selectedAlphasData.value = [];
        return;
      }
      loadingComparisonData.value = true;
      error.value = '';
      const promises = newSelectedIds.map(id =>
        axios.get(`${API_BASE_URL}/api/v1/alphas/${id}`, {
             headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token')}` }
        })
          .then(res => res.data)
          .catch(err => {
            console.error(`获取Alpha ${id} 详情失败:`, err);
            ElMessage.error(`获取Alpha ${id} 数据失败: ${err.response?.data?.detail || err.message}`);
            return null;
          })
      );
      const results = await Promise.all(promises);
      selectedAlphasData.value = results.filter(alpha => alpha !== null);
      loadingComparisonData.value = false;
      if (selectedAlphasData.value.length === 0 && newSelectedIds.length > 0) {
          error.value = "未能加载任何所选Alpha的详细数据。请检查Alpha ID是否正确或尝试其他Alpha。";
      }
    };

    const pnlChartData = computed(() => {
      if (!selectedAlphasData.value || selectedAlphasData.value.length === 0) return { labels: [], datasets: [] };

      let allDates = new Set();
      selectedAlphasData.value.forEach(alpha => {
          if (alpha.pnl_data_json && Array.isArray(alpha.pnl_data_json)) { // [[timestamp, value], ...]
              alpha.pnl_data_json.forEach(dp => allDates.add(new Date(dp[0]).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })));
          } else if (alpha.pnl_data_json?.dates && Array.isArray(alpha.pnl_data_json.dates)) { // {"dates": [], "values": []}
              alpha.pnl_data_json.dates.forEach(d => allDates.add(new Date(d).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })));
          }
      });
      const labels = Array.from(allDates).sort((a, b) => new Date(a) - new Date(b));
      if (labels.length === 0 && selectedAlphasData.value.some(a => a.pnl_data_json)) {
          // Fallback if no common dates found or dates are not in expected format
          // This might happen if pnl_data_json is just an array of values without dates
          const maxLength = Math.max(...selectedAlphasData.value.map(a =>
              Array.isArray(a.pnl_data_json) ? a.pnl_data_json.length : (a.pnl_data_json?.values?.length || 0)
          ));
          if (maxLength > 0) labels = Array.from({length: maxLength}, (_, i) => `T${i + 1}`);
      }


      const datasets = selectedAlphasData.value.map((alpha, index) => {
        let pnlValues = [];
        if (alpha.pnl_data_json && Array.isArray(alpha.pnl_data_json)) { // [[ts, val]]
            const pnlMap = new Map(alpha.pnl_data_json.map(dp => [new Date(dp[0]).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' }), dp[1]]));
            pnlValues = labels.map(label => pnlMap.get(label) || null); // Align with common labels
        } else if (alpha.pnl_data_json?.values && Array.isArray(alpha.pnl_data_json.values)) { // {"dates":[], "values":[]}
            // This assumes dates in pnl_data_json.dates align with global labels if used directly
            pnlValues = alpha.pnl_data_json.values;
            // If lengths don't match global labels, alignment is needed (complex, simplified here)
        }

        return {
          label: `Alpha ${alpha.id.substring(0,8)}`,
          data: pnlValues,
          borderColor: chartColors[index % chartColors.length],
          backgroundColor: chartBgColors[index % chartBgColors.length],
          tension: 0.1,
          fill: false,
          pointRadius: 2,
          pointHoverRadius: 4
        };
      });
      return { labels, datasets };
    });

    const pnlChartOptions = ref({
        responsive: true, maintainAspectRatio: false,
        plugins: { title: { display: true, text: 'PnL 曲线叠加对比', font:{size: 16} }, legend: { position: 'top'}, tooltip:{mode: 'index', intersect: false}},
        scales: { x: { title: {display: true, text: '日期'} }, y: { title: {display: true, text: '累积PnL'} } }
    });

    const metricsChartData = (oos = false) => {
      if (!selectedAlphasData.value || selectedAlphasData.value.length === 0) return { labels: [], datasets: [] };
      const labels = selectedAlphasData.value.map(a => `${a.expression.substring(0,15)}... (${a.id.substring(0,5)})`);

      // Define which metrics to plot and their display names
      const metricsToPlot = [
          { key: 'sharpe', name: 'Sharpe 比率' },
          { key: 'returns', name: '总回报率' },
          { key: 'max_drawdown', name: '最大回撤' },
          { key: 'sortino_ratio', name: '索提诺比率' },
          { key: 'win_rate', name: '胜率 (%)' } // Assuming win_rate is 0-1, multiply by 100 if needed
      ];

      const datasets = metricsToPlot.map((metricInfo, metricIndex) => {
        return {
          label: metricInfo.name,
          data: selectedAlphasData.value.map(alpha => {
            const stats = oos ? alpha.oos_stats_json : alpha.is_stats_json;
            let value = stats && stats[metricInfo.key] !== undefined ? parseFloat(stats[metricInfo.key]) : 0;
            if (metricInfo.key === 'win_rate' && value <= 1 && value >= 0) value *= 100; // Convert to percentage
            return value;
          }),
          backgroundColor: chartColors[metricIndex % chartColors.length],
          borderColor: chartColors[metricIndex % chartColors.length],
          borderWidth: 1
        };
      });
      return { labels, datasets };
    };
    const isMetricsChartData = computed(() => metricsChartData(false));
    const oosMetricsChartData = computed(() => metricsChartData(true));

    const metricsChartOptions = (titleSuffix) => ({
      responsive: true, maintainAspectRatio: false, indexAxis: 'x',
      plugins: {
        title: { display: true, text: `关键性能指标对比 ${titleSuffix}`, font:{size: 16} },
        legend: { position: 'top' },
        tooltip: { mode: 'index', intersect: false }
      },
      scales: {
        x: { stacked: false, title: { display: true, text: 'Alphas (表达式片段与ID)' } },
        y: { stacked: false, title: { display: true, text: '指标值' }, ticks: { callback: value => formatNumber(value, 2) } }
      }
    });
    const metricsChartOptionsIS = computed(() => metricsChartOptions('(样本内 IS)'));
    const metricsChartOptionsOOS = computed(() => metricsChartOptions('(样本外 OOS)'));

    return {
      selectedAlphaIds, searchableAlphas, alphaSearchLoading, searchAlphas,
      selectedAlphasData, loadingComparisonData, error, activeTab, selectionAttempted,
      handleSelectionChange,
      pnlChartData, pnlChartOptions,
      isMetricsChartData, oosMetricsChartData, metricsChartOptionsIS, metricsChartOptionsOOS,
      formatNumber, getFitnessColor
    };
  }
};
</script>

<style scoped>
.alpha-comparison-container { padding: 20px; }
.card-header { font-size: 1.2em; font-weight: bold; display: flex; justify-content: space-between; align-items: center; }
.alpha-selection-area { margin-bottom: 20px; }
.charts-loading-spinner { min-height: 200px; display:flex; align-items:center; justify-content:center; }
.chart-wrapper { position: relative; height: 450px; margin-top: 15px; }
.el-select-dropdown__item span { padding: 0 2px; } /* Adjust padding for better fit */
.el-select-dropdown__item span:first-child { /* Alpha name/id */
  display: inline-block;
  max-width: 70%; /* Adjust as needed */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}
.el-select-dropdown__item span:last-child { /* Fitness score */
  float: right;
  margin-left: 10px; /* Ensure some space */
  vertical-align: middle;
}
</style>
