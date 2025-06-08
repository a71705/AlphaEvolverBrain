// src/components/__tests__/FitnessChart.spec.js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { shallowMount, mount } from '@vue/test-utils';
import FitnessChart from '@/components/FitnessChart.vue';
// import { Line } from 'vue-chartjs'; // vue-chartjs Line component

// Mock Chart.js library itself and its components
// This is crucial as Chart.js relies heavily on Canvas API not fully available in test env.
vi.mock('chart.js', () => {
  const mockChartInstance = {
    update: vi.fn(),
    destroy: vi.fn(),
    data: { labels: [], datasets: [] }, // Mock data structure
    options: {}, // Mock options
  };
  return {
    Chart: vi.fn(() => mockChartInstance), // Mock the Chart constructor
    // Mock individual components Chart.js registers
    Title: vi.fn(),
    Tooltip: vi.fn(),
    Legend: vi.fn(),
    LineElement: vi.fn(),
    CategoryScale: vi.fn(),
    LinearScale: vi.fn(),
    PointElement: vi.fn(),
    Filler: vi.fn(),
    // Default export for ChartJS.register
    default: {
        register: vi.fn()
    }
  };
});

// Mock vue-chartjs's Line component
// We are testing our FitnessChart component, not the Line component itself.
vi.mock('vue-chartjs', () => ({
  Line: {
    name: 'MockedLineChart',
    props: ['data', 'options'],
    template: '<div class="mocked-line-chart">Line Chart Mock</div>',
  },
}));


describe('FitnessChart.vue', () => {
  beforeEach(() => {
    // Reset mocks if necessary, though vi.mock above is module-level
    // vi.clearAllMocks(); // If Chart or Line constructor spies need clearing
  });

  it('应在没有数据时显示 "暂无适应度数据可供展示"', () => {
    const wrapper = mount(FitnessChart, { // Mount to see ElEmpty
      props: {
        fitnessData: [],
        loading: false,
      }
    });
    expect(wrapper.findComponent({ name: 'ElEmpty' }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'ElEmpty' }).props('description')).toBe('暂无适应度数据可供展示');
    expect(wrapper.findComponent({ name: 'MockedLineChart' }).exists()).toBe(false);
  });

  it('应在加载数据时显示加载指示器', () => {
    const wrapper = shallowMount(FitnessChart, { // Shallow is fine if Line is mocked
      props: {
        fitnessData: [],
        loading: true,
      }
    });
    // v-loading is a directive, check for its effect if possible or a loading class/element
    // The component has its own .chart-loading-spinner div
    expect(wrapper.find('.chart-loading-spinner').exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'MockedLineChart' }).exists()).toBe(false);
  });

  it('接收到有效 fitnessData 时应渲染图表组件', async () => {
    const fitnessData = [
      { iteration: 1, fitness: 0.5, avg_fitness: 0.4 },
      { iteration: 2, fitness: 0.6, avg_fitness: 0.45 },
    ];
    const wrapper = mount(FitnessChart, { // Use mount to ensure Line component gets props
      props: {
        fitnessData: [], // Start empty
        loading: false,
      }
    });

    // Initially, no chart
    expect(wrapper.findComponent({ name: 'MockedLineChart' }).exists()).toBe(false);

    // Update props
    await wrapper.setProps({ fitnessData: fitnessData });
    await wrapper.vm.$nextTick(); // Wait for watcher and DOM update

    const lineChart = wrapper.findComponent({ name: 'MockedLineChart' });
    expect(lineChart.exists()).toBe(true);

    // Verify data passed to the (mocked) Line chart component
    const chartDataProp = lineChart.props('data');
    expect(chartDataProp.labels).toEqual(['1', '2']);
    expect(chartDataProp.datasets.length).toBe(2); // best_fitness and avg_fitness
    expect(chartDataProp.datasets[0].label).toBe('最佳适应度');
    expect(chartDataProp.datasets[0].data).toEqual([0.5, 0.6]);
    expect(chartDataProp.datasets[1].label).toBe('平均适应度');
    expect(chartDataProp.datasets[1].data).toEqual([0.4, 0.45]);
  });

  it('当 fitnessData 更新时，图表数据应相应更新', async () => {
    const initialData = [{ iteration: 1, fitness: 0.1 }];
    const wrapper = mount(FitnessChart, {
      props: { fitnessData: initialData, loading: false }
    });

    let lineChart = wrapper.findComponent({ name: 'MockedLineChart' });
    expect(lineChart.props('data').datasets[0].data).toEqual([0.1]);

    const newData = [
        { iteration: 1, fitness: 0.1 },
        { iteration: 2, fitness: 0.2, avg_fitness: 0.15 }
    ];
    await wrapper.setProps({ fitnessData: newData });
    await wrapper.vm.$nextTick();

    lineChart = wrapper.findComponent({ name: 'MockedLineChart' }); // Re-find after update
    expect(lineChart.props('data').labels).toEqual(['1', '2']);
    expect(lineChart.props('data').datasets[0].data).toEqual([0.1, 0.2]);
    expect(lineChart.props('data').datasets[1].data).toEqual([undefined, 0.15]); // avg_fitness for first point was undefined
  });

  // TODO:
  // - Test chartOptions prop being passed correctly.
  // - Test localError state when data processing fails (if such logic is added).
});
