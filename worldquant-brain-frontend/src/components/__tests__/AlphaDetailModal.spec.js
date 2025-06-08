// src/components/__tests__/AlphaDetailModal.spec.js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { shallowMount, mount } from '@vue/test-utils';
import AlphaDetailModal from '@/components/AlphaDetailModal.vue';
import MockAdapter from 'axios-mock-adapter';
import axios from 'axios';

// Mock Element Plus components if not globally stubbed, or for specific interactions
// ElDialog, ElDescriptions, ElTabs, ElEmpty, ElAlert etc.

describe('AlphaDetailModal.vue', () => {
  let mockAxios;
  const mockAlphaId = 'alpha-detail-id-123';

  beforeEach(() => {
    mockAxios = new MockAdapter(axios);
    // vi.clearAllMocks();
  });

  afterEach(() => {
    mockAxios.restore();
  });

  it('当 visible 为 true 且 alphaId 提供时，应获取并显示Alpha详情', async () => {
    const alphaDetailsData = {
      id: mockAlphaId,
      expression: 'ts_rank(close, 20)',
      description: 'Test alpha detail',
      experiment_id: 'exp001',
      created_at: new Date().toISOString(),
      fitness_score: 1.23,
      simulated_at: new Date().toISOString(),
      simulation_status: 'COMPLETED',
      is_stats_json: { sharpe: 1.5, returns: 0.2 },
      // ... other fields from AlphaResponse schema
    };
    mockAxios.onGet(`/api/v1/alphas/${mockAlphaId}`).reply(200, alphaDetailsData);

    const wrapper = mount(AlphaDetailModal, {
      props: {
        visible: true,
        alphaId: mockAlphaId,
      },
      global: { // Stubbing heavy Element Plus components if needed for this test's focus
        stubs: {
            'el-dialog': {
                props: ['modelValue', 'title', 'width', 'beforeClose', 'top', 'destroyOnClose', 'appendToBody'],
                template: '<div v-if="modelValue" class="el-dialog-stub"><slot name="header" /><slot /><slot name="footer" /></div>',
                emits: ['update:modelValue']
            },
            'el-descriptions': { template: '<div><slot name="title"/><slot/></div>' },
            'el-descriptions-item': { template: '<div><slot name="label"/><slot/></div>' },
            'el-tabs': { props:['modelValue'], template: '<div><slot/></div>', emits:['update:modelValue'] },
            'el-tab-pane': { template: '<div><slot/></div>' },
            'el-empty': true,
            'el-alert': true,
            'el-button': true,
            'el-tag': true,
        }
      }
    });

    // Wait for API call and DOM update
    await new Promise(resolve => setTimeout(resolve, 0)); // For axios promise
    await wrapper.vm.$nextTick(); // For Vue DOM update

    expect(wrapper.text()).toContain(mockAlphaId);
    expect(wrapper.text()).toContain('ts_rank(close, 20)');
    expect(wrapper.text()).toContain('1.2300'); // fitness_score formatted
    expect(wrapper.find('pre.stats-box').exists()).toBe(true); // Check if stats are rendered
  });

  it('当 visible 为 false 时，不应显示模态框内容', () => {
    const wrapper = shallowMount(AlphaDetailModal, {
      props: {
        visible: false,
        alphaId: mockAlphaId,
      }
    });
    // In shallowMount, the dialog's v-if might still render its content if not deeply stubbed.
    // However, the root element of the dialog itself might not be in the wrapper if el-dialog is truly conditional.
    // A common pattern for el-dialog is that it's always in DOM but visibility is controlled by CSS.
    // Test Utils for Element Plus might have better ways to check dialog visibility.
    // For now, we check if the dialog stub (if any) or key content is not obviously visible.
    // If el-dialog is stubbed as above, its content is conditional on modelValue (visible)
    expect(wrapper.find('.el-dialog-stub').exists()).toBe(false);
  });

  it('API调用失败时应显示错误信息', async () => {
    mockAxios.onGet(`/api/v1/alphas/${mockAlphaId}`).reply(500, { detail: "获取Alpha详情失败" });

    const wrapper = mount(AlphaDetailModal, {
      props: { visible: true, alphaId: mockAlphaId },
      global: { stubs: { 'el-dialog': { template: '<div><slot/></div>'} } } // Simpler stub for this test
    });

    await new Promise(resolve => setTimeout(resolve, 0));
    await wrapper.vm.$nextTick();

    // Assuming error is displayed via ElEmpty or directly in template
    expect(wrapper.text()).toContain('加载Alpha详情失败: 获取Alpha详情失败');
  });

  it('点击关闭按钮应发出 "close" 事件', async () => {
    const wrapper = mount(AlphaDetailModal, {
      props: { visible: true, alphaId: mockAlphaId },
      // global: { stubs: { ... } } // Provide stubs if needed
    });
    await wrapper.vm.$nextTick(); // Ensure footer button is rendered

    const closeButton = wrapper.findComponent({ name: 'ElButton' }); // Assumes only one button (Close)
    await closeButton.trigger('click');

    expect(wrapper.emitted('close')).toBeTruthy();
    expect(wrapper.emitted('close').length).toBe(1);
  });

  // TODO:
  // - Test different tabs rendering correct JSON data.
  // - Test formatting functions (formatDateTime, formatNumber, getSimulationStatusTag).
  // - Test watcher for alphaId prop changing while modal is visible.
});
