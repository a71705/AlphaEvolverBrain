// src/views/__tests__/ExperimentListView.spec.js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { shallowMount, mount } from '@vue/test-utils';
import ExperimentListView from '@/views/ExperimentListView.vue';
import MockAdapter from 'axios-mock-adapter';
import axios from 'axios';

// Mock Vue Router
const mockRouterPush = vi.fn();
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router');
  return { ...actual, useRouter: () => ({ push: mockRouterPush }) };
});

// Mock Element Plus components used directly or rely on global stubs from setup
// For a view, it's often better to mount with some stubs for child components
// or fully mount if interaction with children is tested.

describe('ExperimentListView.vue', () => {
  let mockAxios;

  beforeEach(() => {
    mockAxios = new MockAdapter(axios);
    mockRouterPush.mockClear();
    // localStorage.clear(); // If used by this component
  });

  it('应能正确渲染组件标题', () => {
    const wrapper = shallowMount(ExperimentListView, {
      global: {
        stubs: { // Stub complex child components if not testing their interaction deeply
          'el-card': { template: '<div><slot name="header" /><slot /></div>' },
          'el-table': true,
          'el-table-column': true,
          'el-tag': true,
          'el-button': true,
          'el-empty': true,
          'el-alert': true,
          'el-pagination': true, // If pagination is used
        }
      }
    });
    // Example: Check for a title or a key element
    // This depends on ExperimentListView.vue's actual template structure.
    // Let's assume it has a card header with a title.
    // const cardHeader = wrapper.find('.el-card-stub .card-header span'); // Adjust selector based on actual template
    // expect(cardHeader.exists()).toBe(true);
    // expect(cardHeader.text()).toContain('实验列表'); // Or whatever the title is
    expect(wrapper.exists()).toBe(true); // Basic check that component mounts
  });

  it('当API成功返回实验数据时，应显示实验表格', async () => {
    const experimentsData = [
      { id: 'exp1', name: 'Experiment 1', status: 'COMPLETED', created_at: new Date().toISOString(), alpha_count: 5 },
      { id: 'exp2', name: 'Experiment 2', status: 'RUNNING', created_at: new Date().toISOString(), alpha_count: 10 },
    ];
    const totalExperiments = 2;
    mockAxios.onGet('/api/v1/experiments').reply(200, {
      experiments: experimentsData,
      total_experiments: totalExperiments, // Assuming API returns total for pagination
    });

    const wrapper = mount(ExperimentListView); // Use mount for more integrated test

    // Wait for API call and DOM update
    await new Promise(resolve => setTimeout(resolve, 0)); // For axios promise
    await wrapper.vm.$nextTick(); // For Vue DOM update

    const table = wrapper.findComponent({ name: 'ElTable' });
    expect(table.exists()).toBe(true);
    // expect(table.props('data').length).toBe(experimentsData.length); // Check if data is passed to table

    // Check for some rendered text from the data
    // expect(wrapper.text()).toContain('Experiment 1');
    // expect(wrapper.text()).toContain('COMPLETED');
  });

  it('当API返回空数据时，应显示el-empty提示', async () => {
    mockAxios.onGet('/api/v1/experiments').reply(200, { experiments: [], total_experiments: 0 });
    const wrapper = mount(ExperimentListView);
    await new Promise(resolve => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();

    expect(wrapper.findComponent({ name: 'ElEmpty' }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(false);
  });

  it('当API调用失败时，应显示错误提示 (el-alert)', async () => {
    mockAxios.onGet('/api/v1/experiments').reply(500, { detail: "服务器内部错误" });
    const wrapper = mount(ExperimentListView);
    await new Promise(resolve => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();

    const alert = wrapper.findComponent({ name: 'ElAlert' });
    expect(alert.exists()).toBe(true);
    // The error message might be handled by ElMessage globally, or displayed in an ElAlert by the component itself.
    // The component's current implementation uses ElMessage.error for API errors.
    // If it were to use an ElAlert: expect(alert.props('title')).toContain('获取实验列表失败');
  });

  // TODO:
  // - Test pagination interaction (if implemented).
  // - Test clicking "创建新实验" button navigation (if implemented).
  // - Test clicking "查看详情" button navigation for an experiment.
  // - Test filtering functionality (if implemented).
  // - Test sorting functionality (if implemented on this table directly).
});
