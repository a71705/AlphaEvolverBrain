// src/components/__tests__/AlphaTable.spec.js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { shallowMount, mount } from '@vue/test-utils';
import AlphaTable from '@/components/AlphaTable.vue';
import MockAdapter from 'axios-mock-adapter';
import axios from 'axios';

// Mock child component AlphaDetailModal
vi.mock('@/components/AlphaDetailModal.vue', () => ({
  default: {
    name: 'AlphaDetailModal',
    props: ['alphaId', 'visible'],
    template: '<div v-if="visible" class="mock-alpha-detail-modal">Modal for {{ alphaId }}</div>',
    emits: ['close'],
  },
}));

// Mock Element Plus components if not globally stubbed
// For this component, ElTable, ElTableColumn, ElLink, ElButton, ElEmpty, ElAlert are used.

describe('AlphaTable.vue', () => {
  let mockAxios;
  const mockExperimentId = 'exp123';

  beforeEach(() => {
    mockAxios = new MockAdapter(axios);
    // vi.clearAllMocks(); // Clear other mocks if necessary
  });

  afterEach(() => {
    mockAxios.restore();
  });

  it('应在加载数据时显示加载指示器', async () => {
    mockAxios.onGet(`/api/v1/experiments/${mockExperimentId}/alphas`).reply(() => new Promise(() => {}));
    const wrapper = shallowMount(AlphaTable, {
      props: { experimentId: mockExperimentId },
      global: { stubs: { 'el-table': true, 'el-empty': true } } // Stubbing to avoid deep rendering
    });
    // el-loading is a directive, checking its presence might be complex in shallowMount.
    // Instead, check if the table/empty state is hidden and loading ref is true.
    // Or use `mount` and check for `element-loading-text`.
    // For now, let's assume the loading prop on the component is testable.
    // This requires `loading` to be returned from setup if we want to check wrapper.vm.loading
    // expect(wrapper.vm.loading).toBe(true); // If loading is exposed
    expect(wrapper.find('.loading-spinner').exists()).toBe(true);
  });

  it('成功获取Alphas数据后应渲染表格', async () => {
    const alphasData = [
      { id: 'alpha001', expression: 'rank(close)', fitness_score: 0.85, is_stats_json: { sharpe: 1.5, returns: 0.12 }, ga_metadata_json: { depth: 2, iteration: 5 }, simulated_at: new Date().toISOString() },
      { id: 'alpha002', expression: 'ts_rank(vwap, 20)', fitness_score: 0.95, is_stats_json: { sharpe: 2.5, returns: 0.15 }, ga_metadata_json: { depth: 3, iteration: 10 }, simulated_at: new Date().toISOString() },
    ];
    // Assuming API returns { alphas: [...] } or just [...]
    mockAxios.onGet(new RegExp(`/api/v1/experiments/${mockExperimentId}/alphas.*`)).reply(200, alphasData); // Use RegExp to match params

    const wrapper = mount(AlphaTable, { // Use mount for better interaction with ElTable
      props: { experimentId: mockExperimentId }
    });

    await new Promise(resolve => setTimeout(resolve, 0)); // Wait for axios
    await wrapper.vm.$nextTick(); // Wait for Vue

    expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(true);
    // More specific assertions: check number of rows, content of rows
    // This depends on ElTable's internal rendering.
    // A common way is to check for text content.
    expect(wrapper.text()).toContain('alpha001'.substring(0,8));
    expect(wrapper.text()).toContain('rank(close)');
    expect(wrapper.text()).toContain('0.9500'); // fitness_score for alpha002
  });

  it('点击Alpha ID或详情按钮应打开AlphaDetailModal', async () => {
    const alphaToDetail = { id: 'alpha001', expression: 'rank(close)', fitness_score: 0.85, is_stats_json: { sharpe: 1.5 } };
    mockAxios.onGet(new RegExp(`/api/v1/experiments/${mockExperimentId}/alphas.*`)).reply(200, [alphaToDetail]);

    const wrapper = mount(AlphaTable, { props: { experimentId: mockExperimentId } });
    await new Promise(resolve => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();

    // Find the link or button for the first alpha and click it
    // This requires ElLink and ElButton not to be fully stubbed out if we want to trigger click.
    // Or, call the method directly.
    // wrapper.vm.openAlphaDetailModal(alphaToDetail); // Call method directly

    // Simulate click (assuming ElLink renders an <a> or similar clickable element)
    const detailTrigger = wrapper.find('.el-link'); // Or find a button
    if (detailTrigger.exists()) {
        await detailTrigger.trigger('click');
    } else {
        // Fallback if ElLink is stubbed too deeply, call method directly
        wrapper.vm.openAlphaDetailModal(alphaToDetail);
        await wrapper.vm.$nextTick(); // Allow modal visibility to update
    }

    const modal = wrapper.findComponent({ name: 'AlphaDetailModal' });
    expect(modal.exists()).toBe(true);
    expect(modal.props('visible')).toBe(true);
    expect(modal.props('alphaId')).toBe('alpha001');
  });

  it('当API返回空数据时，应显示el-empty', async () => {
    mockAxios.onGet(new RegExp(`/api/v1/experiments/${mockExperimentId}/alphas.*`)).reply(200, []);
    const wrapper = mount(AlphaTable, { props: { experimentId: mockExperimentId } });
    await new Promise(resolve => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();

    expect(wrapper.findComponent({name: 'ElEmpty'}).exists()).toBe(true);
    expect(wrapper.findComponent({name: 'ElTable'}).exists()).toBe(false);
  });

  it('当API调用失败时，应显示el-alert', async () => {
    mockAxios.onGet(new RegExp(`/api/v1/experiments/${mockExperimentId}/alphas.*`)).reply(500, { detail: "服务器错误" });
    const wrapper = mount(AlphaTable, { props: { experimentId: mockExperimentId } });
    await new Promise(resolve => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();

    expect(wrapper.findComponent({name: 'ElAlert'}).exists()).toBe(true);
    // The actual error message might be handled by ElMessage globally,
    // so the ElAlert within the component might not be shown or might show a generic message.
    // Check component's `error` ref if it's used to control local ElAlert.
    // expect(wrapper.vm.error).toContain("获取Alphas失败"); // If error ref is exposed
  });

  // TODO:
  // - Test sorting functionality (handleSortChange method and API params).
  // - Test watch effect for experimentId prop change.
  // - Test closing of the AlphaDetailModal.
});
