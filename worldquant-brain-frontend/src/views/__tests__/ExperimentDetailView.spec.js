// src/views/__tests__/ExperimentDetailView.spec.js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { shallowMount, mount } from '@vue/test-utils';
import ExperimentDetailView from '@/views/ExperimentDetailView.vue';
import MockAdapter from 'axios-mock-adapter';
import axios from 'axios';

// Mock Vue Router (useRoute for params, useRouter for navigation if any)
const mockExperimentId = 'exp-test-123';
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router');
  return {
    ...actual,
    useRoute: () => ({
      params: { experimentId: mockExperimentId },
    }),
    useRouter: () => ({
      push: vi.fn(), // Mock push if used for navigation from this view
    }),
  };
});

// Mock child components for shallower tests if needed, or mount fully
// For this view, AlphaTable and FitnessChart are significant children.
vi.mock('@/components/AlphaTable.vue', () => ({
  default: {
    name: 'AlphaTable',
    props: ['experimentId'],
    template: '<div class="mock-alpha-table">AlphaTable for {{ experimentId }}</div>',
  },
}));
vi.mock('@/components/FitnessChart.vue', () => ({
  default: {
    name: 'FitnessChart',
    props: ['fitnessData', 'loading'],
    template: '<div class="mock-fitness-chart">FitnessChart (loading: {{ loading }})</div>',
  },
}));


describe('ExperimentDetailView.vue', () => {
  let mockAxios;

  beforeEach(() => {
    mockAxios = new MockAdapter(axios);
    // vi.clearAllMocks(); // If other global mocks need clearing
  });

  afterEach(() => {
    mockAxios.restore();
  });

  it('应在加载数据时显示加载指示器', async () => {
    // Prevent API call from resolving immediately
    mockAxios.onGet(`/api/v1/experiments/${mockExperimentId}`).reply(() => new Promise(() => {}));

    const wrapper = mount(ExperimentDetailView, {
      global: { stubs: { /* ElementPlus components if not testing their rendering deeply */ } }
    });

    expect(wrapper.attributes('element-loading-text')).toContain('正在加载实验详情...');
  });

  it('成功获取实验数据后应显示实验详情', async () => {
    const experimentData = {
      id: mockExperimentId,
      name: 'Test Experiment Detail',
      status: 'RUNNING',
      description: 'Detailed description here.',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      current_progress: 50,
      current_depth: 1,
      current_iteration_at_depth: 5,
      ga_config_json: { random_seed: 12345, fitness_history: [{iteration:1, best_fitness:0.5}] },
      // ... other fields as per ExperimentResponse schema
    };
    mockAxios.onGet(`/api/v1/experiments/${mockExperimentId}`).reply(200, experimentData);

    const wrapper = mount(ExperimentDetailView);

    await new Promise(resolve => setTimeout(resolve, 0)); // Wait for axios
    await wrapper.vm.$nextTick(); // Wait for Vue DOM update

    expect(wrapper.text()).toContain('实验详情: Test Experiment Detail');
    expect(wrapper.text()).toContain(mockExperimentId);
    expect(wrapper.text()).toContain('RUNNING');
    expect(wrapper.findComponent({ name: 'AlphaTable' }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'FitnessChart' }).exists()).toBe(true);
  });

  it('获取实验数据失败时应显示错误信息', async () => {
    mockAxios.onGet(`/api/v1/experiments/${mockExperimentId}`).reply(500, { detail: "服务器错误" });
    const wrapper = mount(ExperimentDetailView);

    await new Promise(resolve => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();

    expect(wrapper.findComponent({ name: 'ElEmpty' }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'ElEmpty' }).props('description')).toContain('加载实验失败: 服务器错误');
  });

  it('应将 fitness_history 从 ga_config_json 传递给 FitnessChart', async () => {
    const fitnessHistoryData = [
      { iteration: 1, best_fitness: 0.5, avg_fitness: 0.4 },
      { iteration: 2, best_fitness: 0.6, avg_fitness: 0.45 },
    ];
    const experimentData = {
      id: mockExperimentId, name: 'Chart Test', status: 'COMPLETED',
      ga_config_json: { fitness_history: fitnessHistoryData },
      current_progress: 100,
    };
    mockAxios.onGet(`/api/v1/experiments/${mockExperimentId}`).reply(200, experimentData);

    const wrapper = mount(ExperimentDetailView);
    await new Promise(resolve => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();

    const chartComponent = wrapper.findComponent({ name: 'FitnessChart' });
    expect(chartComponent.exists()).toBe(true);

    // Check the prop passed to the (mocked) chart component
    const expectedFormattedData = fitnessHistoryData.map(item => ({
        iteration: item.iteration,
        fitness: item.best_fitness,
        avg_fitness: item.avg_fitness
    }));
    expect(chartComponent.props('fitnessData')).toEqual(expectedFormattedData);
  });

  // TODO:
  // - Test polling mechanism (might require vi.useFakeTimers and advanceTimersByTime).
  // - Test computed properties like progressPercentage and getStatusTagType with various inputs.
  // - Test onUnmounted behavior (clearing interval).
});
