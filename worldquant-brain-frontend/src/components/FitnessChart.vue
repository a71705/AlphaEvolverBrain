// src/components/FitnessChart.vue
<template>
  <div class="fitness-chart-container">
    <Line v-if="chartDataInternal.datasets && chartDataInternal.datasets.length > 0 && !loading && !localError" :data="chartDataInternal" :options="chartOptions" />
    <div v-if="loading" v-loading="loading" element-loading-text="正在加载图表数据..." class="chart-loading-spinner"></div>
    <el-empty v-if="!loading && (localError || !chartDataInternal.datasets || chartDataInternal.datasets.length === 0)"
              :description="localError ? `图表加载失败: ${localError}` : '暂无适应度数据可供展示'">
    </el-empty>
  </div>
</template>

<script>
import { ref, watch, toRefs, onMounted } from 'vue';
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Filler // For area under line, if needed
} from 'chart.js';
import { ElMessage } from 'element-plus'; // For error messages

// 注册 Chart.js 组件
ChartJS.register(
  Title,
  Tooltip,
  Legend,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Filler
);

export default {
  name: 'FitnessChart',
  components: {
    Line
  },
  props: {
    fitnessData: { // 预期格式: [{ iteration: 1, fitness: 0.5, avg_fitness: 0.4, ... }, ...]
      type: Array,
      default: () => []
    },
    loading: { // Prop to indicate data is loading from parent
      type: Boolean,
      default: false,
    }
  },
  setup(props) {
    const { fitnessData, loading: propLoading } = toRefs(props);
    const chartDataInternal = ref({
      labels: [],
      datasets: []
    });
    const localError = ref('');


    const chartOptions = ref({
      responsive: true,
      maintainAspectRatio: false,
      animation: {
          duration: 500 // Shorter animation for updates
      },
      plugins: {
        legend: {
          position: 'top',
        },
        title: {
          display: true,
          text: '适应度演化趋势',
          font: { size: 16, weight: 'bold' },
          padding: { top: 10, bottom: 20 }
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            label: function(context) {
                let label = context.dataset.label || '';
                if (label) {
                    label += ': ';
                }
                if (context.parsed.y !== null) {
                    label += context.parsed.y.toFixed(4); // Format tooltip value
                }
                return label;
            }
          }
        }
      },
      scales: {
        x: {
          title: {
            display: true,
            text: '迭代次数 / 代数',
            font: { size: 14 }
          },
          grid: {
            display: false // Hide x-axis grid lines for cleaner look
          }
        },
        y: {
          title: {
            display: true,
            text: '适应度得分',
            font: { size: 14 }
          },
          beginAtZero: false,
          ticks: {
            callback: function(value) {
                return value.toFixed(3); // Format y-axis ticks
            }
          }
        }
      },
      interaction: { // For hover effects, etc.
          mode: 'nearest',
          axis: 'x',
          intersect: false
      }
    });

    watch([fitnessData, propLoading], ([newData, newLoading]) => {
      localError.value = ''; // Reset local error on new data/loading change
      if (newLoading) {
        // Data is loading externally, chart can show its own spinner or wait
        // chartDataInternal.value = { labels: [], datasets: [] }; // Optionally clear old data
        return;
      }
      if (!newData || newData.length === 0) {
        if (!newLoading) { // Only set error if not loading and no data
          // localError.value = '无有效的适应度数据。'; // Or let el-empty handle it
        }
        chartDataInternal.value = { labels: [], datasets: [] };
        return;
      }

      try {
        const labels = newData.map(item => String(item.iteration || item.generation || item.id || 'N/A'));
        const bestFitnessValues = newData.map(item => item.fitness !== undefined ? item.fitness : item.best_fitness);

        const datasets = [
          {
            label: '最佳适应度',
            backgroundColor: 'rgba(54, 162, 235, 0.2)', // Blue
            borderColor: 'rgb(54, 162, 235)',
            borderWidth: 2,
            pointBackgroundColor: 'rgb(54, 162, 235)',
            pointRadius: 3,
            pointHoverRadius: 5,
            tension: 0.2, // Smoother lines
            data: bestFitnessValues,
            fill: true, // Area under line
          }
        ];

        const avgFitnessValues = newData.map(item => item.avg_fitness);
        if (avgFitnessValues.every(val => val !== undefined && val !== null)) { // Check if all values are valid
          datasets.push({
            label: '平均适应度',
            backgroundColor: 'rgba(255, 99, 132, 0.2)', // Red
            borderColor: 'rgb(255, 99, 132)',
            borderWidth: 2,
            pointBackgroundColor: 'rgb(255, 99, 132)',
            pointRadius: 3,
            pointHoverRadius: 5,
            tension: 0.2,
            data: avgFitnessValues,
            fill: true,
          });
        }

        chartDataInternal.value = {
          labels: labels,
          datasets: datasets
        };
      } catch (e) {
        console.error("处理图表数据时出错:", e);
        localError.value = `图表数据处理错误: ${e.message}`;
        ElMessage.error(localError.value);
        chartDataInternal.value = { labels: [], datasets: [] };
      }
    }, { immediate: true, deep: true });

    return {
      chartDataInternal, // Renamed to avoid conflict with prop
      chartOptions,
      localError // Expose localError to template
    };
  }
};
</script>

<style scoped>
.fitness-chart-container {
  position: relative;
  min-height: 350px; /* Increased min-height for better visibility */
  width: 100%;
  padding: 10px; /* Add some padding around the chart */
  background-color: #fff; /* Optional: background for the chart area */
  border-radius: 4px; /* Optional: match card styling */
  /* box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1); Optional: add shadow like cards */
}
.chart-loading-spinner {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.8); /* Slightly more opaque */
  z-index: 10;
}
/* Ensure canvas itself resizes correctly if needed, though vue-chartjs handles it well */
/* canvas {
  max-width: 100%;
  max-height: 100%;
} */
</style>
